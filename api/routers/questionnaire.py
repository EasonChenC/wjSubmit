# api/routers/questionnaire.py
"""
Questionnaire routing module

Provides questionnaire analysis, submission, and reverse item detection APIs.
"""

import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from playwright.async_api import async_playwright

from ..models import (
    AnalyzeRequest, DataResponse, AnalyzeResponse, QuestionResponse,
    SubmitRequest, TaskStatusResponse, SubmitResult,
    DetectionRequest, DetectionResponse, DetectionResult
)
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter
from core.reverse_item_detector import ReverseItemDetector
from core.schema import QuestionType
from ai.config import AIConfigManager
from ai.client import AIClient
from ai.reverse_detector import override_schema_with_ai_detection


router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"])

# Global task storage (use Redis in production)
tasks: Dict[str, dict] = {}


# ========== Questionnaire Analysis API ==========

@router.post("/analyze", response_model=DataResponse)
async def analyze_questionnaire(request: AnalyzeRequest):
    """
    Analyze questionnaire structure

    Fetch questionnaire HTML by URL and parse its structure,
    returning question list, question type statistics, etc.
    Optionally uses AI to detect reverse items if enabled.

    Args:
        request: Request containing questionnaire URL and use_ai flag

    Returns:
        Questionnaire analysis result
    """
    try:
        # 1. Use Playwright to fetch HTML
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(str(request.url), wait_until='networkidle', timeout=30000)
                html = await page.content()
            finally:
                await browser.close()

        # 2. Use RuleBasedAnalyzer to analyze
        analyzer = RuleBasedAnalyzer()
        schema = analyzer.analyze(html, str(request.url))

        # 3. AI detection (optional)
        detection_method = "keyword"
        if request.use_ai:
            manager = AIConfigManager.get_instance()
            if not manager.is_configured():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI is not configured. Please configure AI settings first."
                )
            config = manager.get_config()
            client = AIClient(config.api_key, config.model, config.base_url)
            await override_schema_with_ai_detection(schema, client)
            detection_method = "ai"

        # 4. Convert to API response format
        scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX]

        questions_data = []
        for question in schema.questions:
            # Check if it's a scale question (hardcoded types OR AI identified)
            is_scale = question.type in scale_types or question.metadata.get('is_scale', False)

            questions_data.append(QuestionResponse(
                id=question.id,
                type=question.type.value,
                label=question.label,
                options=question.options,
                required=question.required,
                is_scale=is_scale,
                is_reverse=question.metadata.get('is_reverse', False),
                reverse_confidence=question.metadata.get('reverse_confidence'),
                detection_method=question.metadata.get('detection_method') if is_scale else None,
                positive_values=question.metadata.get('positive_values') if is_scale else None,
                negative_values=question.metadata.get('negative_values') if is_scale else None
            ))

        # Count scale questions (both hardcoded types and AI-identified)
        scale_questions_count = sum(
            1 for q in schema.questions if (q.type in scale_types or q.metadata.get('is_scale', False))
        )

        response_data = AnalyzeResponse(
            activity_id=schema.activity_id,
            url=schema.url,
            total_questions=schema.metadata['total_questions'],
            question_types=schema.metadata['identified_types'],
            questions=questions_data,
            scale_questions=scale_questions_count,
            reverse_items=schema.metadata.get('reverse_items', []),
            detection_method=detection_method
        )

        return DataResponse(
            success=True,
            message="Questionnaire analyzed successfully",
            data=response_data
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Questionnaire analysis failed: {str(e)}"
        )


# ========== Questionnaire Submission API ==========

async def submit_one_questionnaire(url: str, schema, answers: dict) -> dict:
    """
    Submit one questionnaire

    Args:
        url: Questionnaire URL
        schema: Questionnaire Schema
        answers: Answer dictionary

    Returns:
        Submission result: {'success': True/False, 'error': 'error message'}
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=1)
        page = await browser.new_page()

        try:
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await asyncio.sleep(random.uniform(1, 2))

            # Use DynamicSubmitter to fill and submit
            submitter = DynamicSubmitter(schema)
            success = await submitter.fill_and_submit(page, answers)

            return {'success': success}

        except Exception as e:
            return {'success': False, 'error': str(e)}

        finally:
            await asyncio.sleep(1)
            await browser.close()


async def submit_questionnaire_task(
    task_id: str, url: str, count: int, mode: str, config: dict
):
    """
    Background task: batch submit questionnaires

    Args:
        task_id: Task ID
        url: Questionnaire URL
        count: Number of submissions
        mode: Submission mode
        config: Mode configuration
    """
    try:
        tasks[task_id]["status"] = "processing"

        # 1. Analyze questionnaire
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                html = await page.content()
            finally:
                await browser.close()

        analyzer = RuleBasedAnalyzer()
        schema = analyzer.analyze(html, url)

        # 2. Create answer generator
        generator = DynamicAnswerGenerator(
            schema=schema,
            high_reliability_mode=(mode == "high_reliability"),
            attitude=config.get("attitude", "positive"),
            add_variation=config.get("add_variation", False),
            variation_ratio=config.get("variation_ratio", 0.05)
        )

        # 3. Batch submit
        success_count = 0
        fail_count = 0

        for i in range(count):
            try:
                # Generate answers
                answers = generator.generate_answers()

                # Submit questionnaire
                result = await submit_one_questionnaire(url, schema, answers)

                if result.get('success'):
                    success_count += 1
                    tasks[task_id]["results"].append({
                        "index": i + 1,
                        "status": "success"
                    })
                else:
                    fail_count += 1
                    tasks[task_id]["results"].append({
                        "index": i + 1,
                        "status": "failed",
                        "error": result.get('error', 'Unknown error')
                    })

                # Update progress
                tasks[task_id]["submitted"] = success_count
                tasks[task_id]["failed"] = fail_count
                tasks[task_id]["progress"] = int((i + 1) / count * 100)

                # Delay (avoid requests too fast)
                if i < count - 1:
                    await asyncio.sleep(random.uniform(3, 5))

            except Exception as e:
                fail_count += 1
                tasks[task_id]["results"].append({
                    "index": i + 1,
                    "status": "failed",
                    "error": str(e)
                })
                tasks[task_id]["failed"] = fail_count

        # 4. Complete
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["end_time"] = datetime.now().isoformat()

    except Exception as e:
        tasks[task_id]["status"] = "failed"
        tasks[task_id]["end_time"] = datetime.now().isoformat()
        tasks[task_id]["error"] = str(e)


@router.post("/submit", response_model=DataResponse)
async def submit_questionnaire(request: SubmitRequest, background_tasks: BackgroundTasks):
    """
    Submit questionnaire (background task)

    Create a background task for batch questionnaire submission.

    Args:
        request: Submit request
        background_tasks: FastAPI background task manager

    Returns:
        Task ID and initial status
    """
    try:
        # Generate task ID
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # Initialize task status
        tasks[task_id] = {
            "task_id": task_id,
            "status": "pending",
            "submitted": 0,
            "failed": 0,
            "total": request.count,
            "progress": 0,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "results": []
        }

        # Get config (handle None value)
        config = request.config.dict() if request.config else {}

        # Add background task
        background_tasks.add_task(
            submit_questionnaire_task,
            task_id, str(request.url), request.count, request.mode, config
        )

        return DataResponse(
            success=True,
            message="Task created, processing in background",
            data={
                "task_id": task_id,
                "status": "processing",
                "submitted": 0,
                "total": request.count
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/submit/{task_id}", response_model=DataResponse)
async def get_task_status(task_id: str):
    """
    Query task status

    Args:
        task_id: Task ID

    Returns:
        Task status information
    """
    if task_id not in tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    task_data = tasks[task_id]

    # Convert to response model
    response_data = TaskStatusResponse(**task_data)

    return DataResponse(
        success=True,
        message="Task status retrieved successfully",
        data=response_data
    )


# ========== Reverse Item Detection API ==========

@router.post("/reverse-items", response_model=DataResponse)
async def detect_reverse_items(request: DetectionRequest):
    """
    Detect reverse items

    Identify reverse items (negative items) in scale questions.

    Args:
        request: Request containing question list

    Returns:
        Reverse item detection result
    """
    try:
        detector = ReverseItemDetector()
        results = []
        reverse_count = 0

        for question in request.questions:
            is_reverse, confidence, keywords = detector.detect(question.label)

            if is_reverse:
                reverse_count += 1

            results.append(DetectionResult(
                id=question.id,
                label=question.label,
                is_reverse=is_reverse,
                confidence=confidence,
                matched_keywords=keywords
            ))

        response_data = DetectionResponse(
            total_questions=len(request.questions),
            reverse_count=reverse_count,
            results=results
        )

        return DataResponse(
            success=True,
            message="Reverse item detection completed successfully",
            data=response_data
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reverse item detection failed: {str(e)}"
        )
