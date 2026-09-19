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
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from playwright.async_api import async_playwright
from playwright.async_api import BrowserContext
from sqlalchemy import select, func, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    AnalyzeRequest, DataResponse, AnalyzeResponse, QuestionResponse,
    SubmitRequest, TaskStatusResponse, SubmitResult, TaskConfigUpdate,
    DetectionRequest, DetectionResponse, DetectionResult, ProxyConfig
)
from core.rule_based_analyzer import RuleBasedAnalyzer
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.dynamic_submitter import DynamicSubmitter
from core.reverse_item_detector import ReverseItemDetector
from core.schema import QuestionType, QuestionnaireSchema
from core.proportion_planner import (
    ELIGIBLE_TYPES,
    ProportionConfigError,
    build_proportion_plan,
)
from ai import ai_config_manager
from ai.client import AIClient
from ai.reverse_detector import override_schema_with_ai_detection
from ai.text_answer_pool import TextareaAnswerPoolGenerator, TextAnswerPoolError
from db.session import get_session, session_scope
from db.models import (
    QuestionnaireTask,
    TaskSubmission,
    TaskTextAnswerPool,
    TaskProportionAnswerPlan,
    AuditLog,
)
from proxy.config import KuaidailiSettings
from proxy.models import ProxyLease
from proxy.service import ProxyService, browser_launch_proxy, create_submission_context
from api.dependencies import get_current_user
from db.models import User


router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"], dependencies=[Depends(get_current_user)])


def _is_admin(user: User) -> bool:
    return bool(user.role and user.role.code == "admin")


def _task_scope(stmt, user: User):
    """Administrators see all tasks; other roles are always owner-scoped."""
    return stmt if _is_admin(user) else stmt.where(QuestionnaireTask.user_id == user.id)


async def _claim_legacy_tasks(session: AsyncSession, user: User) -> None:
    """Assign pre-authentication tasks to the first/current administrator.

    Legacy rows were intentionally created with user_id=NULL.  Once the user
    module is enabled, claiming them preserves their visibility while keeping
    all newly-created rows owner-scoped.
    """
    if not _is_admin(user):
        return
    legacy = (await session.scalars(
        select(QuestionnaireTask).where(QuestionnaireTask.user_id.is_(None))
    )).all()
    if legacy:
        for task in legacy:
            task.user_id = user.id
        await session.commit()


async def _task_checkpoint(session: AsyncSession, task: QuestionnaireTask):
    rows = (await session.execute(
        select(TaskSubmission.submit_index, TaskSubmission.status)
        .where(TaskSubmission.task_id == task.id)
    )).all()
    successes = {index for index, state in rows if state == "success"}
    failed = sum(1 for _, state in rows if state == "failed")
    task.submitted_count = len(successes)
    task.failed_count = failed
    task.progress = min(100, int(len(successes) * 100 / max(task.total_count, 1)))
    return successes, failed


async def _next_attempt_no(session: AsyncSession, task_id, submit_index: int) -> int:
    latest = await session.scalar(
        select(func.max(TaskSubmission.attempt_no)).where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.submit_index == submit_index,
        )
    )
    return (latest or 0) + 1


async def _previous_answers(session: AsyncSession, task_id, submit_index: int):
    return await session.scalar(
        select(TaskSubmission.generated_answers)
        .where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.submit_index == submit_index,
            TaskSubmission.generated_answers.is_not(None),
        )
        .order_by(TaskSubmission.attempt_no.desc())
        .limit(1)
    )


def proxy_config_from_settings(settings: KuaidailiSettings) -> dict:
    """Return the non-secret default task policy from environment settings."""

    return {
        "enabled": settings.enabled,
        "provider": "kuaidaili",
        "area": settings.default_area,
        "carrier": settings.default_carrier,
        "rotate_per_submission": settings.rotate_per_submission,
        "dedup": settings.dedup,
        "verify_exit": settings.verify_exit,
        "location_match": settings.location_match,
        "required": settings.required,
        "max_acquire_attempts": settings.max_acquire_attempts,
    }


def disabled_proxy_config() -> dict:
    """Return a complete task policy that explicitly disables proxy usage.

    Questionnaire tasks are opt-in: provider credentials and KDL_ENABLED only
    make the provider available; they must not silently enable it for a task
    whose create request omitted/disabled the proxy option.
    """
    return {
        "enabled": False,
        "provider": "kuaidaili",
        "area": "",
        "carrier": 0,
        "rotate_per_submission": True,
        "dedup": True,
        "verify_exit": True,
        "location_match": "relaxed",
        "required": True,
        "max_acquire_attempts": 3,
    }


def proxy_settings_from_task(task_row, base: KuaidailiSettings) -> KuaidailiSettings:
    """Combine persisted task policy with environment-only provider credentials."""

    settings = replace(
        base,
        enabled=task_row.proxy_enabled,
        default_area=task_row.proxy_area or "",
        default_carrier=task_row.proxy_carrier,
        rotate_per_submission=task_row.proxy_rotate_per_submission,
        dedup=task_row.proxy_dedup,
        verify_exit=task_row.proxy_verify_exit,
        location_match=task_row.proxy_location_match,
        required=task_row.proxy_required,
        max_acquire_attempts=task_row.proxy_max_acquire_attempts,
    )
    settings.validate(require_credentials=settings.enabled)
    return settings


def apply_proxy_config(task_row, proxy_config: dict) -> None:
    task_row.proxy_enabled = proxy_config["enabled"]
    task_row.proxy_provider = proxy_config["provider"] if proxy_config["enabled"] else None
    task_row.proxy_area = proxy_config["area"] or None
    task_row.proxy_carrier = proxy_config["carrier"]
    task_row.proxy_rotate_per_submission = proxy_config["rotate_per_submission"]
    task_row.proxy_dedup = proxy_config["dedup"]
    task_row.proxy_verify_exit = proxy_config["verify_exit"]
    task_row.proxy_location_match = proxy_config["location_match"]
    task_row.proxy_required = proxy_config["required"]
    task_row.proxy_max_acquire_attempts = proxy_config["max_acquire_attempts"]


def record_proxy_lease(submission, lease: ProxyLease | None) -> None:
    if lease is None:
        return
    submission.proxy_host = lease.endpoint.host
    submission.proxy_port = lease.endpoint.port
    submission.proxy_requested_area = lease.requested_area
    submission.proxy_reported_location = lease.verified_location
    submission.proxy_city_code = lease.endpoint.city_code or None
    submission.proxy_carrier = lease.endpoint.carrier or None
    submission.proxy_exit_ip = lease.exit_ip
    submission.proxy_remaining_seconds = lease.remaining_seconds()
    submission.proxy_latency_ms = lease.latency_ms
    submission.proxy_attempts = lease.acquisition_attempt


def is_ai_text_question(question) -> bool:
    """Return whether a question participates in AI text answer generation."""
    return question.type in {QuestionType.TEXT, QuestionType.TEXTAREA}


async def prepare_text_answer_pools(
    session: AsyncSession,
    task_row: QuestionnaireTask,
    schema: QuestionnaireSchema,
) -> dict[str, list[str]]:
    """Generate/resume all AI single-line and multiline text pools.

    Each database row stores one question's answers in submission order. A
    commit follows every valid batch so a restarted background task resumes at
    the first missing index instead of regenerating completed answers.
    """
    if not task_row.ai_text_enabled:
        return {}

    questions = [
        {"id": question.id, "label": question.label}
        for question in schema.questions
        if is_ai_text_question(question)
    ]
    if not questions:
        task_row.ai_text_status = "ready"
        task_row.ai_text_generated_count = task_row.total_count
        task_row.ai_text_error = None
        await session.commit()
        return {}

    if not await ai_config_manager.is_configured(session):
        raise TextAnswerPoolError("AI configuration is disabled or incomplete")
    ai_config = await ai_config_manager.get_config(session)
    task_row.ai_text_status = "generating"
    task_row.ai_text_model = ai_config.model
    task_row.ai_text_error = None
    await session.commit()

    result = await session.execute(
        select(TaskTextAnswerPool).where(TaskTextAnswerPool.task_id == task_row.id)
    )
    existing = {row.question_id: row for row in result.scalars().all()}
    pools: dict[str, TaskTextAnswerPool] = {}
    for question in questions:
        row = existing.get(question["id"])
        if row is None:
            row = TaskTextAnswerPool(
                task_id=task_row.id,
                question_id=question["id"],
                question_label=question["label"],
                answers=[],
            )
            session.add(row)
        pools[question["id"]] = row
    await session.commit()

    lengths = {len(row.answers or []) for row in pools.values()}
    if len(lengths) != 1:
        raise TextAnswerPoolError("Persisted text answer pools have inconsistent lengths")
    generated_count = lengths.pop() if lengths else 0
    if generated_count > task_row.total_count:
        raise TextAnswerPoolError("Persisted text answer pool exceeds task submission count")

    task_row.ai_text_generated_count = generated_count
    await session.commit()

    generator = TextareaAnswerPoolGenerator(
        AIClient(ai_config.api_key, ai_config.model, ai_config.base_url),
        max_attempts=task_row.ai_text_max_attempts,
    )
    while generated_count < task_row.total_count:
        await session.refresh(task_row)
        if task_row.cancel_requested:
            raise asyncio.CancelledError("Task cancelled while generating text answers")

        current_batch_size = min(
            task_row.ai_text_batch_size,
            task_row.total_count - generated_count,
        )
        batch = await generator.generate_batch(questions, current_batch_size)
        for local_answers in batch:
            for question in questions:
                row = pools[question["id"]]
                row.answers = [*(row.answers or []), local_answers[question["id"]]]

        generated_count += current_batch_size
        task_row.ai_text_generated_count = generated_count
        await session.commit()

    task_row.ai_text_status = "ready"
    task_row.ai_text_error = None
    await session.commit()
    return {question_id: list(row.answers or []) for question_id, row in pools.items()}


def text_overrides_for_submission(
    pools: dict[str, list[str]], submission_index: int
) -> dict[str, str]:
    """Return the exact pre-generated text answers for a 1-based index."""
    if not pools:
        return {}
    offset = submission_index - 1
    overrides: dict[str, str] = {}
    for question_id, answers in pools.items():
        if offset < 0 or offset >= len(answers):
            raise TextAnswerPoolError(
                f"Missing persisted answer for {question_id} at submission {submission_index}"
            )
        overrides[question_id] = answers[offset]
    return overrides


def _ratio_metadata(question, *, is_scale: bool, allow_scale: bool) -> dict:
    eligible = (
        question.type in ELIGIBLE_TYPES
        and bool(question.options)
        and (allow_scale or not is_scale)
    )
    minimum = maximum = None
    if question.type == QuestionType.CHECKBOX:
        minimum = int((question.strategy.params or {}).get("min", 1 if question.required else 0))
        maximum = int((question.strategy.params or {}).get("max", len(question.options)))
    return {
        "ratio_eligible": eligible,
        "ratio_kind": (
            "multiple" if question.type == QuestionType.CHECKBOX else "single"
        ) if eligible else None,
        "selection_min": minimum,
        "selection_max": maximum,
        "parent_question_id": question.metadata.get("base_id") if question.type == QuestionType.MATRIX else None,
        "ratio_zero_values": (
            [question.metadata["other_option_value"]]
            if question.metadata.get("other_option_value") is not None else []
        ),
    }


def _question_display_metadata(questions: list) -> dict[str, dict]:
    """Assign actual top-to-bottom display order, grouping matrix/text subitems."""
    result: dict[str, dict] = {}
    group_positions: dict[str, int] = {}
    matrix_rows: dict[str, int] = {}
    next_position = 0
    for question in questions:
        group_id = (
            question.metadata.get("parent_question")
            or question.metadata.get("base_id")
            or question.id
        )
        if group_id not in group_positions:
            next_position += 1
            group_positions[group_id] = next_position
        position = group_positions[group_id]
        display_key = str(position)
        if question.type == QuestionType.MATRIX:
            matrix_rows[group_id] = matrix_rows.get(group_id, 0) + 1
            display_key = f"{position}.{matrix_rows[group_id]}"
        result[question.id] = {
            "display_order": position,
            "ratio_display_key": display_key if question.type in ELIGIBLE_TYPES else None,
        }
    return result


async def prepare_proportion_answer_plans(
    session: AsyncSession,
    task_row: QuestionnaireTask,
    schema: QuestionnaireSchema,
) -> dict[int, dict]:
    """Create/reopen the complete deterministic proportional answer plan."""
    enabled_configs = [
        item for item in (task_row.proportion_config or {}).get("questions", [])
        if item.get("enabled", True)
    ]
    if not enabled_configs:
        task_row.proportion_plan_status = "disabled"
        return {}

    result = await session.execute(
        select(TaskProportionAnswerPlan)
        .where(TaskProportionAnswerPlan.task_id == task_row.id)
        .order_by(TaskProportionAnswerPlan.submit_index)
    )
    existing = result.scalars().all()
    if existing:
        if len(existing) != task_row.total_count or [row.submit_index for row in existing] != list(range(1, task_row.total_count + 1)):
            raise ProportionConfigError("Persisted proportional answer plan is incomplete")
        task_row.proportion_plan_status = "ready"
        task_row.proportion_plan_count = len(existing)
        await session.commit()
        return {row.submit_index: dict(row.answers) for row in existing}

    task_row.proportion_plan_status = "pending"
    await session.commit()
    plans = build_proportion_plan(
        schema,
        task_row.proportion_config or {},
        task_row.total_count,
        seed=task_row.proportion_plan_seed,
    )
    for index, answers in enumerate(plans, 1):
        session.add(TaskProportionAnswerPlan(
            task_id=task_row.id,
            submit_index=index,
            answers=answers,
        ))
    task_row.proportion_plan_status = "ready"
    task_row.proportion_plan_count = len(plans)
    await session.commit()
    return {index: answers for index, answers in enumerate(plans, 1)}


# ========== Questionnaire Analysis API ==========

@router.post("/analyze", response_model=DataResponse)
async def analyze_questionnaire(
    request: AnalyzeRequest, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)
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
        detection_method = "structure" if request.analysis_mode == "proportional" else "keyword"
        if request.analysis_mode == "proportional":
            # Proportional mode needs only stable structure/options. It does not
            # call AI or infer positive/negative/reverse semantics.
            schema.metadata['reverse_items'] = []
        elif request.use_ai:
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
        display_metadata = _question_display_metadata(schema.questions)
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
                negative_values=question.metadata.get('negative_values') if is_scale else None,
                **_ratio_metadata(
                    question,
                    is_scale=is_scale,
                    allow_scale=request.analysis_mode == "proportional",
                ),
                **display_metadata[question.id],
            ))

        # Count scale questions (both hardcoded types and AI-identified)
        scale_questions_count = sum(
            1 for q in schema.questions if (q.type in scale_types or q.metadata.get('is_scale', False))
        )
        reverse_items = schema.metadata.get('reverse_items', [])

        # 5. Persist analyzed schema as a new task (status=pending, no submit
        # config yet — that's filled in by /submit)
        task_row = QuestionnaireTask(
            user_id=current_user.id,
            url=str(request.url),
            title=schema.metadata.get('title') or None,
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
            title=schema.metadata.get('title', ''),
            description=schema.metadata.get('description', ''),
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

async def submit_one_questionnaire(
    url: str,
    schema,
    answers: dict,
    context: BrowserContext,
    lease: ProxyLease | None = None,
) -> dict:
    """
    Submit one questionnaire

    Args:
        url: Questionnaire URL
        schema: Questionnaire Schema
        answers: Answer dictionary
        context: A fresh browser context for this submission. When proxy mode
            is enabled, the context is already bound to one proxy endpoint.
        lease: Optional metadata for the selected proxy lease.

    Returns:
        Submission result: {'success': True/False, 'error': 'error message'}
    """
    page = await context.new_page()
    try:
        await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(random.uniform(1, 2))

        submitter = DynamicSubmitter(schema)
        success = await submitter.fill_and_submit(page, answers)

        result = {'success': success}
        if lease:
            result['proxy'] = {
                'endpoint': lease.endpoint.log_label,
                'requested_area': lease.requested_area,
                'exit_ip': lease.exit_ip,
                'verified_location': lease.verified_location,
                'latency_ms': lease.latency_ms,
                'attempt': lease.acquisition_attempt,
            }
        return result

    except Exception as e:
        return {'success': False, 'error': str(e)}

    finally:
        await page.close()


async def submit_questionnaire_task(task_id: str, execution_token: str):
    """Execute or resume a task from its persisted successful-index checkpoint."""
    async with session_scope() as session:
        task_row = await session.get(QuestionnaireTask, task_id)
        if task_row is None or str(task_row.execution_token) != execution_token:
            return
        try:
            success_indexes, _ = await _task_checkpoint(session, task_row)
            if len(success_indexes) >= task_row.total_count:
                task_row.status = "completed"
                task_row.progress = 100
                task_row.finished_at = datetime.now(timezone.utc)
                task_row.execution_token = None
                await session.commit()
                return

            task_row.status = "processing"
            task_row.started_at = task_row.started_at or datetime.now(timezone.utc)
            task_row.finished_at = None
            task_row.heartbeat_at = datetime.now(timezone.utc)
            task_row.error_message = None
            await session.commit()

            schema = QuestionnaireSchema.from_dict(task_row.analyzed_schema)
            generator = DynamicAnswerGenerator(
                schema=schema, mode=task_row.submit_mode,
                attitude=task_row.attitude, add_variation=task_row.add_variation,
                variation_ratio=float(task_row.variation_ratio),
            )
            text_answer_pools = await prepare_text_answer_pools(session, task_row, schema)
            proportion_plans = await prepare_proportion_answer_plans(session, task_row, schema)
            base_proxy_settings = KuaidailiSettings.from_env() if task_row.proxy_enabled else KuaidailiSettings(enabled=False)
            proxy_settings = proxy_settings_from_task(task_row, base_proxy_settings)
            proxy_service = ProxyService(proxy_settings) if proxy_settings.enabled else None
            cancelled = False

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=not task_row.browser_debug,
                    slow_mo=100 if task_row.browser_debug else 0,
                    proxy=browser_launch_proxy(proxy_settings),
                )
                try:
                    for submit_index in range(1, task_row.total_count + 1):
                        if submit_index in success_indexes:
                            continue
                        while submit_index not in success_indexes:
                            await session.refresh(task_row)
                            if str(task_row.execution_token) != execution_token:
                                return
                            if task_row.cancel_requested:
                                cancelled = True
                                break

                            attempt_no = await _next_attempt_no(session, task_row.id, submit_index)
                            submission = TaskSubmission(
                                task_id=task_row.id, submit_index=submit_index,
                                attempt_no=attempt_no, execution_no=task_row.execution_no,
                                status="pending", started_at=datetime.now(timezone.utc),
                            )
                            session.add(submission)
                            context = None
                            lease = None
                            max_submit_attempts = (
                                min(task_row.submit_max_attempts, task_row.proportion_max_submit_attempts)
                                if task_row.submit_mode == "proportional" else task_row.submit_max_attempts
                            )
                            try:
                                answers = await _previous_answers(session, task_row.id, submit_index)
                                if answers is None:
                                    overrides = dict(proportion_plans.get(submit_index, {}))
                                    text_overrides = text_overrides_for_submission(text_answer_pools, submit_index)
                                    overlap = set(overrides) & set(text_overrides)
                                    if overlap:
                                        raise ValueError(f"Conflicting answer overrides: {sorted(overlap)}")
                                    overrides.update(text_overrides)
                                    answers = generator.generate_answers(overrides)
                                submission.generated_answers = answers
                                succeeded = False
                                last_error = "Unknown error"
                                for inner_attempt in range(1, max_submit_attempts + 1):
                                    try:
                                        lease, context = await create_submission_context(
                                            browser=browser, settings=proxy_settings, service=proxy_service,
                                            context_options={
                                                "locale": "zh-CN", "timezone_id": "Asia/Shanghai",
                                                "viewport": {"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},
                                            },
                                        )
                                        result = await submit_one_questionnaire(task_row.url, schema, answers, context=context, lease=lease)
                                        record_proxy_lease(submission, lease)
                                        if result.get("success"):
                                            succeeded = True
                                            break
                                        last_error = result.get("error", "Unknown error")
                                    except Exception as exc:
                                        last_error = str(exc)
                                        record_proxy_lease(submission, lease)
                                    finally:
                                        if context is not None:
                                            await context.close()
                                            context = None
                                    if inner_attempt < max_submit_attempts:
                                        await asyncio.sleep(min(inner_attempt, 2))

                                if succeeded:
                                    submission.status = "success"
                                    success_indexes.add(submit_index)
                                    task_row.submitted_count = len(success_indexes)
                                    task_row.consecutive_failure_count = 0
                                else:
                                    submission.status = "failed"
                                    submission.error_message = last_error
                                    submission.failure_stage = "business_submission"
                                    task_row.failed_count += 1
                                    task_row.consecutive_failure_count += 1
                            except Exception as exc:
                                submission.status = "failed"
                                submission.error_message = str(exc)
                                submission.failure_stage = "submission_execution"
                                task_row.failed_count += 1
                                task_row.consecutive_failure_count += 1
                            finally:
                                if context is not None:
                                    await context.close()
                                submission.finished_at = datetime.now(timezone.utc)

                            task_row.progress = min(100, int(task_row.submitted_count * 100 / max(task_row.total_count, 1)))
                            task_row.heartbeat_at = datetime.now(timezone.utc)
                            await session.commit()

                            if submission.status == "success":
                                if task_row.submitted_count < task_row.total_count:
                                    await asyncio.sleep(random.uniform(3, 5))
                                break
                            if task_row.consecutive_failure_count >= task_row.max_consecutive_failures:
                                raise RuntimeError(f"Task paused after {task_row.consecutive_failure_count} consecutive failures")
                            # Interruptible exponential backoff.
                            for _ in range(min(5 * (2 ** min(task_row.consecutive_failure_count - 1, 3)), 60)):
                                await asyncio.sleep(1)
                                await session.refresh(task_row)
                                if task_row.cancel_requested or str(task_row.execution_token) != execution_token:
                                    cancelled = task_row.cancel_requested
                                    break
                            if cancelled:
                                break
                        if cancelled:
                            break
                finally:
                    if proxy_service:
                        await proxy_service.aclose()
                    await browser.close()

            await _task_checkpoint(session, task_row)
            if cancelled:
                task_row.status = "cancelled"
            elif task_row.submitted_count >= task_row.total_count:
                task_row.status = "completed"
                task_row.progress = 100
            else:
                task_row.status = "failed"
            task_row.finished_at = datetime.now(timezone.utc)
            task_row.execution_token = None
            await session.commit()
        except asyncio.CancelledError:
            await session.rollback()
            task_row = await session.get(QuestionnaireTask, task_id)
            if task_row and str(task_row.execution_token) == execution_token:
                task_row.status = "cancelled"
                task_row.finished_at = datetime.now(timezone.utc)
                task_row.execution_token = None
                await session.commit()
        except Exception as exc:
            await session.rollback()
            task_row = await session.get(QuestionnaireTask, task_id)
            if task_row and str(task_row.execution_token) == execution_token:
                task_row.status = "failed"
                task_row.error_message = str(exc)
                task_row.finished_at = datetime.now(timezone.utc)
                task_row.execution_token = None
                await session.commit()


@router.post("/submit", response_model=DataResponse)
async def submit_questionnaire(
    request: SubmitRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user),
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
        task_row = await session.scalar(select(QuestionnaireTask).where(QuestionnaireTask.id == request.task_id, QuestionnaireTask.user_id == current_user.id))
        if task_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task not found: {request.task_id}. Call /analyze first."
            )

        config = request.config.model_dump() if request.config else {}
        proxy_config = (
            request.proxy.model_dump()
            if request.proxy is not None
            else disabled_proxy_config()
        )
        if proxy_config["enabled"]:
            environment_proxy = KuaidailiSettings.from_env()
            environment_proxy.validate(require_credentials=True)

        ai_text_config = request.ai_text.model_dump() if request.ai_text else {
            "enabled": False,
            "batch_size": 20,
            "max_generation_attempts": 3,
        }
        if ai_text_config["enabled"] and not await ai_config_manager.is_configured(session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI is not configured. Please configure AI settings first."
            )

        proportion_config = (
            request.proportion_config.model_dump()
            if request.proportion_config is not None else None
        )
        enabled_ratio_configs = [
            item for item in (proportion_config or {}).get("questions", [])
            if item.get("enabled", True)
        ]
        if proportion_config is not None:
            proportion_config["exclude_scale_questions"] = request.mode != "proportional"
        if request.mode == "proportional" or enabled_ratio_configs:
            if task_row.detection_method != "structure":
                # AI/high-reliability analysis may combine reliability handling
                # for scale questions with ratios for non-scale questions.
                if request.mode == "proportional":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Proportional mode requires a task analyzed with analysis_mode=proportional",
                    )
            try:
                # Validate feasibility before the background task starts. The
                # exact same deterministic plan is persisted by the worker.
                build_proportion_plan(
                    QuestionnaireSchema.from_dict(task_row.analyzed_schema),
                    proportion_config or {},
                    request.count,
                    seed=(proportion_config or {}).get("seed", 0),
                )
            except ProportionConfigError as exc:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        task_row.status = "pending"
        task_row.submit_mode = request.mode
        task_row.total_count = request.count
        task_row.attitude = config.get("attitude", "positive")
        task_row.add_variation = config.get("add_variation", False)
        task_row.variation_ratio = config.get("variation_ratio", 0.05)
        task_row.browser_debug = config.get("debug", False)
        task_row.submit_max_attempts = config.get("max_submit_attempts", 10)
        task_row.ai_text_enabled = ai_text_config["enabled"]
        task_row.ai_text_batch_size = ai_text_config["batch_size"]
        task_row.ai_text_max_attempts = ai_text_config["max_generation_attempts"]
        task_row.ai_text_status = "pending" if ai_text_config["enabled"] else "disabled"
        task_row.ai_text_generated_count = 0
        task_row.ai_text_model = None
        task_row.ai_text_error = None
        task_row.proportion_config = proportion_config
        task_row.proportion_plan_status = "pending" if enabled_ratio_configs else "disabled"
        task_row.proportion_plan_count = 0
        task_row.proportion_plan_seed = (proportion_config or {}).get("seed", 0)
        task_row.proportion_max_submit_attempts = (proportion_config or {}).get("max_submit_attempts", 10)
        apply_proxy_config(task_row, proxy_config)
        task_row.cancel_requested = False
        task_row.submitted_count = 0
        task_row.failed_count = 0
        task_row.progress = 0
        task_row.consecutive_failure_count = 0
        task_row.execution_no = 1
        task_row.execution_token = uuid.uuid4()
        task_row.resume_count = 0
        task_row.heartbeat_at = datetime.now(timezone.utc)
        await session.commit()

        background_tasks.add_task(
            submit_questionnaire_task,
            request.task_id,
            str(task_row.execution_token),
        )

        return DataResponse(
            success=True,
            message="Task created, processing in background",
            data={
                "task_id": request.task_id,
                "status": "processing",
                "submitted": 0,
                "total": request.count,
                "proxy": proxy_config,
                "ai_text": ai_text_config,
                "proportion_plan_status": task_row.proportion_plan_status,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/tasks", response_model=DataResponse)
async def list_tasks(
    q: str | None = None,
    owner_id: str | None = None,
    offset: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    await _claim_legacy_tasks(session, current_user)
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(QuestionnaireTask.title.ilike(pattern), QuestionnaireTask.url.ilike(pattern), User.username.ilike(pattern)))
    if owner_id and _is_admin(current_user):
        filters.append(QuestionnaireTask.user_id == owner_id)

    count_stmt = _task_scope(
        select(func.count(QuestionnaireTask.id)).join(User, QuestionnaireTask.user_id == User.id, isouter=True).where(*filters), current_user
    )
    total = await session.scalar(count_stmt)
    stmt = _task_scope(
        select(QuestionnaireTask)
        .options(selectinload(QuestionnaireTask.user))
        .join(User, QuestionnaireTask.user_id == User.id, isouter=True)
        .where(*filters),
        current_user,
    ).order_by(QuestionnaireTask.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 100))
    rows = (await session.scalars(stmt)).all()
    items = [{
        "task_id": str(row.id),
        "title": row.title or "\u672a\u547d\u540d\u95ee\u5377",
        "url": row.url,
        "status": row.status,
        "submitted": row.submitted_count,
        "failed": row.failed_count,
        "total": row.total_count,
        "progress": row.progress,
        "remaining": max(row.total_count - row.submitted_count, 0),
        "can_resume": row.status in ("cancelled", "failed") and row.submitted_count < row.total_count,
        "start_time": (row.started_at or row.created_at).isoformat(),
        "end_time": row.finished_at.isoformat() if row.finished_at else None,
        "creator_id": str(row.user_id) if row.user_id else None,
        "creator_username": row.user.username if row.user else "\u672a\u77e5\u7528\u6237",
        "proxy": {
            "enabled": row.proxy_enabled,
            "provider": row.proxy_provider or "kuaidaili",
            "area": row.proxy_area or "",
            "carrier": row.proxy_carrier,
            "rotate_per_submission": row.proxy_rotate_per_submission,
            "dedup": row.proxy_dedup,
            "verify_exit": row.proxy_verify_exit,
            "location_match": row.proxy_location_match,
            "required": row.proxy_required,
            "max_acquire_attempts": row.proxy_max_acquire_attempts,
        },
    } for row in rows]
    return DataResponse(success=True, message="Tasks retrieved", data={"items": items, "total": total or 0})


@router.get("/tasks/{task_id}/analysis", response_model=DataResponse)
async def get_task_analysis(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    task = await session.scalar(
        _task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    schema = QuestionnaireSchema.from_dict(task.analyzed_schema)
    scale_types = {QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX}
    display_metadata = _question_display_metadata(schema.questions)
    questions = []
    for question in schema.questions:
        is_scale = question.type in scale_types or question.metadata.get("is_scale", False)
        questions.append(QuestionResponse(
            id=question.id,
            type=question.type.value,
            label=question.label,
            options=question.options,
            required=question.required,
            is_scale=is_scale,
            is_reverse=question.metadata.get("is_reverse", False),
            reverse_confidence=question.metadata.get("reverse_confidence"),
            detection_method=question.metadata.get("detection_method") if is_scale else None,
            positive_values=question.metadata.get("positive_values") if is_scale else None,
            negative_values=question.metadata.get("negative_values") if is_scale else None,
            **_ratio_metadata(question, is_scale=is_scale, allow_scale=task.detection_method == "structure"),
            **display_metadata[question.id],
        ).model_dump())
    return DataResponse(success=True, message="Task analysis retrieved", data={
        "task_id": str(task.id), "title": task.title or "\u672a\u547d\u540d\u95ee\u5377",
        "url": task.url, "activity_id": task.activity_id, "platform": task.platform,
        "detection_method": task.detection_method, "total_questions": task.total_questions,
        "scale_questions": task.scale_questions, "reverse_items": task.reverse_items or [],
        "questions": questions,
    })


def _task_config_payload(task: QuestionnaireTask) -> dict:
    """Return the persisted execution configuration in an editor-friendly shape."""
    return {
        "task_id": str(task.id),
        "mode": task.submit_mode,
        "attitude": task.attitude,
        "add_variation": task.add_variation,
        "variation_ratio": float(task.variation_ratio),
        "debug": task.browser_debug,
        "max_submit_attempts": task.submit_max_attempts,
        "proxy": {
            "enabled": task.proxy_enabled,
            "provider": task.proxy_provider or "kuaidaili",
            "area": task.proxy_area or "",
            "carrier": task.proxy_carrier,
            "rotate_per_submission": task.proxy_rotate_per_submission,
            "dedup": task.proxy_dedup,
            "verify_exit": task.proxy_verify_exit,
            "location_match": task.proxy_location_match,
            "required": task.proxy_required,
            "max_acquire_attempts": task.proxy_max_acquire_attempts,
        },
        "ai_text": {
            "enabled": task.ai_text_enabled,
            "batch_size": task.ai_text_batch_size,
            "max_generation_attempts": task.ai_text_max_attempts,
        },
        "proportion_config": task.proportion_config,
    }


@router.get("/tasks/{task_id}/config", response_model=DataResponse)
async def get_task_config(task_id: str, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    task = await session.scalar(_task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return DataResponse(success=True, message="Task configuration retrieved", data=_task_config_payload(task))


@router.patch("/tasks/{task_id}/config", response_model=DataResponse)
async def update_task_config(task_id: str, request: TaskConfigUpdate, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    task = await session.scalar(_task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status in ("pending", "processing"):
        raise HTTPException(status_code=409, detail="请先停止任务，再修改配置")
    data = request.model_dump(exclude_unset=True)
    mode = data.get("mode", task.submit_mode)
    if mode == "proportional" and data.get("proportion_config", task.proportion_config) is None:
        raise HTTPException(status_code=422, detail="比例模式必须提供比例配置")
    ai_text = data.get("ai_text")
    if ai_text and ai_text.get("enabled") and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="仅管理员可启用 AI 文本生成")
    if ai_text and ai_text.get("enabled") and not await ai_config_manager.is_configured(session):
        raise HTTPException(status_code=422, detail="AI 尚未配置或未启用")
    task.submit_mode = mode
    for source, attr in (("attitude", "attitude"), ("add_variation", "add_variation"), ("variation_ratio", "variation_ratio"), ("debug", "browser_debug"), ("max_submit_attempts", "submit_max_attempts")):
        if source in data:
            setattr(task, attr, data[source])
    if "proxy" in data and data["proxy"] is not None:
        proxy = data["proxy"]
        if proxy.get("enabled"):
            KuaidailiSettings.from_env().validate(require_credentials=True)
        apply_proxy_config(task, proxy)
    if ai_text is not None:
        task.ai_text_enabled = ai_text["enabled"]
        task.ai_text_batch_size = ai_text["batch_size"]
        task.ai_text_max_attempts = ai_text["max_generation_attempts"]
        task.ai_text_status = "pending" if ai_text["enabled"] else "disabled"
    if "proportion_config" in data:
        proportion = data["proportion_config"]
        enabled = [x for x in (proportion or {}).get("questions", []) if x.get("enabled", True)]
        if enabled:
            try:
                build_proportion_plan(QuestionnaireSchema.from_dict(task.analyzed_schema), proportion, task.total_count, seed=proportion.get("seed", 0))
            except ProportionConfigError as exc:
                raise HTTPException(status_code=422, detail=str(exc))
        task.proportion_config = proportion
        task.proportion_plan_status = "pending" if enabled else "disabled"
        task.proportion_plan_count = 0
        task.proportion_plan_seed = (proportion or {}).get("seed", 0)
        task.proportion_max_submit_attempts = (proportion or {}).get("max_submit_attempts", 10)
        # A persisted plan is derived from the old percentages. Remove it so
        # the next resume deterministically rebuilds all still-needed answers.
        await session.execute(delete(TaskProportionAnswerPlan).where(TaskProportionAnswerPlan.task_id == task.id))
    session.add(AuditLog(user_id=current_user.id, action="task.config.update", resource_type="questionnaire_task", resource_id=str(task.id), metadata_json={"fields": list(data)}))
    await session.commit()
    return DataResponse(success=True, message="Task configuration saved", data=_task_config_payload(task))


@router.delete("/tasks/{task_id}", response_model=DataResponse)
async def delete_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Permission denied")
    task = await session.scalar(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    session.add(AuditLog(user_id=current_user.id, action="task.delete", resource_type="questionnaire_task", resource_id=str(task.id), metadata_json={"title": task.title or ""}))
    await session.delete(task)
    await session.commit()
    return DataResponse(success=True, message="Task deleted", data={"task_id": task_id})


@router.get("/submit/{task_id}", response_model=DataResponse)
async def get_task_status(task_id: str, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Query task status

    Args:
        task_id: Task ID

    Returns:
        Task status information
    """
    task_row = await session.scalar(_task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user))
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
        title=task_row.title,
        status=task_row.status,
        submitted=task_row.submitted_count,
        failed=task_row.failed_count,
        total=task_row.total_count,
        progress=task_row.progress,
        remaining=max(task_row.total_count - task_row.submitted_count, 0),
        cancel_requested=task_row.cancel_requested,
        can_resume=task_row.status in ("cancelled", "failed") and task_row.submitted_count < task_row.total_count,
        execution_no=task_row.execution_no,
        resume_count=task_row.resume_count,
        consecutive_failure_count=task_row.consecutive_failure_count,
        max_consecutive_failures=task_row.max_consecutive_failures,
        start_time=(task_row.started_at or task_row.created_at).isoformat(),
        end_time=task_row.finished_at.isoformat() if task_row.finished_at else None,
        proxy=ProxyConfig(
            enabled=task_row.proxy_enabled,
            provider=task_row.proxy_provider or "kuaidaili",
            area=task_row.proxy_area or "",
            carrier=task_row.proxy_carrier,
            rotate_per_submission=task_row.proxy_rotate_per_submission,
            dedup=task_row.proxy_dedup,
            verify_exit=task_row.proxy_verify_exit,
            location_match=task_row.proxy_location_match,
            required=task_row.proxy_required,
            max_acquire_attempts=task_row.proxy_max_acquire_attempts,
        ),
        ai_text_enabled=task_row.ai_text_enabled,
        ai_text_status=task_row.ai_text_status,
        ai_text_generated_count=task_row.ai_text_generated_count,
        ai_text_error=task_row.ai_text_error,
        proportion_plan_status=task_row.proportion_plan_status,
        proportion_plan_count=task_row.proportion_plan_count,
        results=[
            SubmitResult(
                index=s.submit_index,
                status=s.status,
                error=s.error_message,
                proxy_endpoint=(
                    f"{s.proxy_host}:{s.proxy_port}" if s.proxy_host and s.proxy_port else None
                ),
                proxy_requested_area=s.proxy_requested_area,
                proxy_reported_location=s.proxy_reported_location,
                proxy_exit_ip=s.proxy_exit_ip,
                proxy_carrier=s.proxy_carrier,
                proxy_remaining_seconds=s.proxy_remaining_seconds,
                proxy_latency_ms=s.proxy_latency_ms,
                proxy_attempts=s.proxy_attempts,
                failure_stage=s.failure_stage,
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


@router.post("/submit/{task_id}/cancel", response_model=DataResponse)
async def cancel_task(task_id: str, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """
    Stop a running task

    Sets cancel_requested on the task row. The background submission loop in
    submit_questionnaire_task polls this flag before starting each new
    submission and stops gracefully once it sees it — an in-flight submission
    (browser already open, mid-fill) is allowed to finish rather than being
    killed outright. Only tasks in 'pending' or 'processing' can be cancelled.

    Args:
        task_id: Task ID

    Returns:
        Updated task status
    """
    task_row = await session.scalar(_task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user))
    if task_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task not found: {task_id}"
        )

    if task_row.status not in ("pending", "processing"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task is already '{task_row.status}' and cannot be cancelled"
        )

    task_row.cancel_requested = True
    await session.commit()

    return DataResponse(
        success=True,
        message="Stop requested, task will stop after the current submission finishes",
        data={"task_id": str(task_row.id), "status": task_row.status}
    )


@router.post("/submit/{task_id}/resume", response_model=DataResponse)
async def resume_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    task = await session.scalar(
        _task_scope(select(QuestionnaireTask).where(QuestionnaireTask.id == task_id), current_user)
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("cancelled", "failed"):
        raise HTTPException(status_code=409, detail="Task is not resumable in its current status")
    await _task_checkpoint(session, task)
    if task.submitted_count >= task.total_count:
        task.status = "completed"
        task.progress = 100
        await session.commit()
        raise HTTPException(status_code=409, detail="Task has already reached its target")
    if task.proxy_enabled:
        KuaidailiSettings.from_env().validate(require_credentials=True)
    if task.ai_text_enabled and not await ai_config_manager.is_configured(session):
        raise HTTPException(status_code=409, detail="AI configuration is unavailable")

    previous_status = task.status
    token = uuid.uuid4()
    # Optimistic conditional update prevents two resume requests from both winning.
    result = await session.execute(
        update(QuestionnaireTask)
        .where(
            QuestionnaireTask.id == task.id,
            QuestionnaireTask.status == previous_status,
            QuestionnaireTask.submitted_count < QuestionnaireTask.total_count,
        )
        .values(
            status="pending", cancel_requested=False, error_message=None,
            finished_at=None, execution_no=QuestionnaireTask.execution_no + 1,
            execution_token=token, resume_count=QuestionnaireTask.resume_count + 1,
            last_resumed_at=datetime.now(timezone.utc), heartbeat_at=datetime.now(timezone.utc),
        )
    )
    if result.rowcount != 1:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Task was resumed by another request")
    session.add(AuditLog(
        user_id=current_user.id, action="task.resume", resource_type="questionnaire_task",
        resource_id=str(task.id), metadata_json={
            "previous_status": previous_status, "submitted_count": task.submitted_count,
            "total_count": task.total_count, "remaining_count": task.total_count - task.submitted_count,
        },
    ))
    await session.commit()
    background_tasks.add_task(submit_questionnaire_task, str(task.id), str(token))
    return DataResponse(success=True, message="Task resume requested", data={
        "task_id": str(task.id), "status": "pending", "submitted": task.submitted_count,
        "total": task.total_count, "remaining": task.total_count - task.submitted_count,
    })


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
