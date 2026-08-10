# api/routers/questionnaire.py
"""
Questionnaire routing module

Provides questionnaire analysis, submission, and reverse item detection APIs.

Flow: analyze_questionnaire fetches+analyzes a questionnaire and persists the
resulting QuestionnaireSchema into questionnaire_tasks.analyzed_schema
(JSONB), returning a task_id. submit_questionnaire takes that task_id and
generates answers directly from the stored schema — the page is never
re-visited or re-analyzed at submit time.
"""

import asyncio
import random
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from playwright.async_api import async_playwright
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    AnalyzeRequest, DataResponse, AnalyzeResponse, QuestionResponse,
    SubmitRequest, TaskStatusResponse, SubmitResult,
    DetectionRequest, DetectionResponse, DetectionResult
)
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter
from core.reverse_item_detector import ReverseItemDetector
from core.schema import QuestionType, QuestionnaireSchema
from ai import ai_config_manager
from ai.client import AIClient
from ai.reverse_detector import override_schema_with_ai_detection
from db.session import get_session, session_scope
from db.models import QuestionnaireTask, TaskSubmission


router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"])


# ========== Questionnaire Analysis API ==========

@router.post("/analyze", response_model=DataResponse)
async def analyze_questionnaire(
    request: AnalyzeRequest, session: AsyncSession = Depends(get_session)
):
    """
    Analyze questionnaire structure

    Fetch questionnaire HTML by URL and parse its structure, persist the
    result to questionnaire_tasks, and return question list, statistics,
    and a task_id. Use that task_id with /submit — no need to pass the URL
    again or re-analyze the page.

    Args:
        request: Request containing questionnaire URL and use_ai flag

    Returns:
        Questionnaire analysis result (includes task_id)
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

        # 3. Reverse item + scale detection
        detection_method = "keyword"
        if request.use_ai:
            if not await ai_config_manager.is_configured(session):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="AI is not configured. Please configure AI settings first."
                )
            config = await ai_config_manager.get_config(session)
            client = AIClient(config.api_key, config.model, config.base_url)
            await override_schema_with_ai_detection(schema, client)
            detection_method = "ai"
        else:
            # No AI: use keyword-based detector to set is_scale/is_reverse
            # and derive positive_values/negative_values for RATING/NPS/MATRIX
            detector = ReverseItemDetector()
            detector.batch_detect(schema.questions)
            schema.metadata['reverse_items'] = [
                q.id for q in schema.questions if q.metadata.get('is_reverse')
            ]

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
        reverse_items = schema.metadata.get('reverse_items', [])

        # 5. Persist analyzed schema as a new task (status=pending, no submit
        # config yet — that's filled in by /submit)
        task_row = QuestionnaireTask(
            url=str(request.url),
            activity_id=schema.activity_id,
            platform=schema.platform,
            analyzed_schema=schema.to_dict(),
            detection_method=detection_method,
            total_questions=schema.metadata.get('total_questions', len(schema.questions)),
            scale_questions=scale_questions_count,
            reverse_items=reverse_items,
            status="pending",
        )
        session.add(task_row)
        await session.commit()

        response_data = AnalyzeResponse(
            task_id=str(task_row.id),
            activity_id=schema.activity_id,
            url=schema.url,
            total_questions=schema.metadata['total_questions'],
            question_types=schema.metadata['identified_types'],
            questions=questions_data,
            scale_questions=scale_questions_count,
            reverse_items=reverse_items,
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
        browser = await p.chromium.launch(headless=False, slow_mo=100)
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


async def submit_questionnaire_task(task_id: str, count: int, mode: str, config: dict):
    """
    Background task: batch submit questionnaires

    Reads the previously analyzed schema from questionnaire_tasks.analyzed_schema
    (populated by analyze_questionnaire) and generates answers directly from it.
    The questionnaire page is never re-visited for analysis here.

    Args:
        task_id: questionnaire_tasks.id (as string)
        count: Number of submissions
        mode: Submission mode
        config: Mode configuration
    """
    async with session_scope() as session:
        task_row = await session.get(QuestionnaireTask, task_id)
        if task_row is None:
            return

        try:
            task_row.status = "processing"
            task_row.submit_mode = mode
            task_row.attitude = config.get("attitude", "positive")
            task_row.add_variation = config.get("add_variation", False)
            task_row.variation_ratio = config.get("variation_ratio", 0.05)
            task_row.total_count = count
            task_row.started_at = datetime.now(timezone.utc)
            await session.commit()

            # Rebuild schema from the stored analysis — no re-fetch/re-analyze
            schema: QuestionnaireSchema = QuestionnaireSchema.from_dict(task_row.analyzed_schema)
            url = task_row.url

            generator = DynamicAnswerGenerator(
                schema=schema,
                mode=mode,
                attitude=config.get("attitude", "positive"),
                add_variation=config.get("add_variation", False),
                variation_ratio=config.get("variation_ratio", 0.05)
            )

            success_count = 0
            fail_count = 0

            for i in range(count):
                submission = TaskSubmission(
                    task_id=task_row.id,
                    submit_index=i + 1,
                    status="pending",
                    started_at=datetime.now(timezone.utc),
                )
                session.add(submission)

                try:
                    answers = generator.generate_answers()
                    result = await submit_one_questionnaire(url, schema, answers)

                    if result.get('success'):
                        success_count += 1
                        submission.status = "success"
                    else:
                        fail_count += 1
                        submission.status = "failed"
                        submission.error_message = result.get('error', 'Unknown error')

                    submission.generated_answers = answers

                except Exception as e:
                    fail_count += 1
                    submission.status = "failed"
                    submission.error_message = str(e)

                submission.finished_at = datetime.now(timezone.utc)

                task_row.submitted_count = success_count
                task_row.failed_count = fail_count
                task_row.progress = int((i + 1) / count * 100)
                await session.commit()

                if i < count - 1:
                    await asyncio.sleep(random.uniform(3, 5))

            task_row.status = "completed"
            task_row.finished_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as e:
            task_row.status = "failed"
            task_row.error_message = str(e)
            task_row.finished_at = datetime.now(timezone.utc)
            await session.commit()


@router.post("/submit", response_model=DataResponse)
async def submit_questionnaire(
    request: SubmitRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    """
    Submit questionnaire (background task)

    Looks up the task created by /analyze via task_id and kicks off batch
    submission in the background, generating answers from the schema that
    was already analyzed and persisted — no re-analysis happens here.

    Args:
        request: Submit request (task_id + count/mode/config)
        background_tasks: FastAPI background task manager

    Returns:
        Task ID and initial status
    """
    try:
        task_row = await session.get(QuestionnaireTask, request.task_id)
        if task_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {request.task_id}. Call /analyze first."
            )

        config = request.config.dict() if request.config else {}

        task_row.status = "pending"
        task_row.submit_mode = request.mode
        task_row.total_count = request.count
        task_row.attitude = config.get("attitude", "positive")
        task_row.add_variation = config.get("add_variation", False)
        task_row.variation_ratio = config.get("variation_ratio", 0.05)
        await session.commit()

        background_tasks.add_task(
            submit_questionnaire_task,
            request.task_id, request.count, request.mode, config
        )

        return DataResponse(
            success=True,
            message="Task created, processing in background",
            data={
                "task_id": request.task_id,
                "status": "processing",
                "submitted": 0,
                "total": request.count
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/submit/{task_id}", response_model=DataResponse)
async def get_task_status(task_id: str, session: AsyncSession = Depends(get_session)):
    """
    Query task status

    Args:
        task_id: Task ID

    Returns:
        Task status information
    """
    task_row = await session.get(QuestionnaireTask, task_id)
    if task_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    result = await session.execute(
        select(TaskSubmission)
        .where(TaskSubmission.task_id == task_row.id)
        .order_by(TaskSubmission.submit_index)
    )
    submissions = result.scalars().all()

    response_data = TaskStatusResponse(
        task_id=str(task_row.id),
        url=task_row.url,
        status=task_row.status,
        submitted=task_row.submitted_count,
        failed=task_row.failed_count,
        total=task_row.total_count,
        progress=task_row.progress,
        start_time=(task_row.started_at or task_row.created_at).isoformat(),
        end_time=task_row.finished_at.isoformat() if task_row.finished_at else None,
        results=[
            SubmitResult(
                index=s.submit_index,
                status=s.status,
                error=s.error_message,
            )
            for s in submissions
            if s.status in ("success", "failed")  # skip in-flight "pending" rows
        ],
    )

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
