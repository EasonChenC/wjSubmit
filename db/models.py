# db/models.py
"""
SQLAlchemy 2.0 Async ORM 模型

与 sql/ 目录下的建表语句一一对应，字段名、类型、约束保持一致。
新增字段请同步更新 sql/ 下的建表脚本（或后续引入 Alembic 迁移）。
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    BigInteger,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Role(Base):
    """角色表，对应 sql/001_roles.sql"""

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="role")

    def __repr__(self) -> str:
        return f"Role(id={self.id}, code={self.code!r})"


class User(Base):
    """用户表，对应 sql/001_users.sql"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False, default=2
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[Optional[str]] = mapped_column(INET)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="users")
    ai_configs: Mapped[list["AIConfigModel"]] = relationship(back_populates="user")
    questionnaire_tasks: Mapped[list["QuestionnaireTask"]] = relationship(back_populates="user")
    sessions: Mapped[list["UserSession"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username!r})"


class UserSession(Base):
    __tablename__ = "user_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    refresh_token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped["User"] = relationship(back_populates="sessions")


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(128))
    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIConfigModel(Base):
    """AI配置表，对应 sql/002_ai_configs.sql

    命名为 AIConfigModel 以避免与 ai/config.py 中现有的 AIConfig dataclass 混淆。
    """

    __tablename__ = "ai_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    api_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="gpt-4o-mini")
    base_url: Mapped[str] = mapped_column(
        String(255), nullable=False, default="https://api.openai.com/v1"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="ai_configs")

    def __repr__(self) -> str:
        return f"AIConfigModel(id={self.id}, user_id={self.user_id}, model={self.model!r})"


class QuestionnaireTask(Base):
    """问卷任务表，对应 sql/003_questionnaire_tasks.sql

    analyzed_schema 存放 analyze 阶段产出的完整 QuestionnaireSchema
    （含 is_scale/is_reverse/positive_values/negative_values 等），
    submit 阶段直接读取该字段生成答案，不重新分析问卷页面。
    """

    __tablename__ = "questionnaire_tasks"
    __table_args__ = (
        CheckConstraint(
            "detection_method IN ('keyword', 'ai', 'structure')", name="ck_questionnaire_tasks_detection_method"
        ),
        CheckConstraint(
            "submit_mode IN ('random', 'high_reliability', 'proportional')", name="ck_questionnaire_tasks_submit_mode"
        ),
        CheckConstraint(
            "attitude IN ('positive', 'negative')", name="ck_questionnaire_tasks_attitude"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
            name="ck_questionnaire_tasks_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_questionnaire_tasks_progress"),
        CheckConstraint(
            "proxy_provider IS NULL OR proxy_provider IN ('kuaidaili')",
            name="ck_questionnaire_tasks_proxy_provider",
        ),
        CheckConstraint(
            "proxy_carrier BETWEEN 0 AND 3", name="ck_questionnaire_tasks_proxy_carrier"
        ),
        CheckConstraint(
            "proxy_location_match IN ('strict', 'relaxed')",
            name="ck_questionnaire_tasks_proxy_location_match",
        ),
        CheckConstraint(
            "proxy_max_acquire_attempts BETWEEN 1 AND 5",
            name="ck_questionnaire_tasks_proxy_attempts",
        ),
        CheckConstraint(
            "ai_text_batch_size BETWEEN 1 AND 50",
            name="ck_questionnaire_tasks_ai_text_batch_size",
        ),
        CheckConstraint(
            "ai_text_max_attempts BETWEEN 1 AND 5",
            name="ck_questionnaire_tasks_ai_text_attempts",
        ),
        CheckConstraint(
            "ai_text_status IN ('disabled', 'pending', 'generating', 'ready', 'failed', 'cancelled')",
            name="ck_questionnaire_tasks_ai_text_status",
        ),
        CheckConstraint(
            "proportion_plan_status IN ('disabled', 'pending', 'ready', 'failed')",
            name="ck_questionnaire_tasks_proportion_status",
        ),
        CheckConstraint(
            "proportion_max_submit_attempts BETWEEN 1 AND 10",
            name="ck_questionnaire_tasks_proportion_attempts",
        ),
        CheckConstraint(
            "submit_max_attempts BETWEEN 1 AND 10",
            name="ck_questionnaire_tasks_submit_attempts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    activity_id: Mapped[Optional[str]] = mapped_column(String(128))
    platform: Mapped[Optional[str]] = mapped_column(String(32))

    analyzed_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    detection_method: Mapped[str] = mapped_column(String(16), nullable=False, default="keyword")
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scale_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reverse_items: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    submit_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="random")
    attitude: Mapped[str] = mapped_column(String(16), nullable=False, default="positive")
    add_variation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    variation_ratio: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False, default=Decimal("0.05"))
    browser_debug: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submit_max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=10)

    proxy_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    proxy_provider: Mapped[Optional[str]] = mapped_column(String(32))
    proxy_area: Mapped[Optional[str]] = mapped_column(String(64))
    proxy_carrier: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    proxy_rotate_per_submission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    proxy_dedup: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    proxy_verify_exit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    proxy_location_match: Mapped[str] = mapped_column(
        String(16), nullable=False, default="relaxed"
    )
    proxy_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    proxy_max_acquire_attempts: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=3
    )

    # AI 单行/多行文本答案池配置与预生成状态。模型凭据仍只保存在 ai_configs。
    ai_text_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_text_batch_size: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=20)
    ai_text_max_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    ai_text_status: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    ai_text_generated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_text_model: Mapped[Optional[str]] = mapped_column(String(128))
    ai_text_error: Mapped[Optional[str]] = mapped_column(Text)

    proportion_config: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    proportion_plan_status: Mapped[str] = mapped_column(String(16), nullable=False, default="disabled")
    proportion_plan_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proportion_plan_seed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    proportion_max_submit_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=10)

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
                        # 由 /submit/{task_id}/cancel 置位；后台提交循环在每次迭代开始时
                        # 轮询该字段（session.refresh），置位后优雅停止，不强行中断进行中的提交

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="questionnaire_tasks")
    submissions: Mapped[list["TaskSubmission"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    text_answer_pools: Mapped[list["TaskTextAnswerPool"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    proportion_answer_plans: Mapped[list["TaskProportionAnswerPlan"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"QuestionnaireTask(id={self.id}, status={self.status!r}, url={self.url!r})"


class TaskSubmission(Base):
    """任务提交明细表，对应 sql/004_task_submissions.sql

    记录一个 QuestionnaireTask 批量提交中每一份的具体执行情况。
    """

    __tablename__ = "task_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'success', 'failed')", name="ck_task_submissions_status"
        ),
        UniqueConstraint("task_id", "submit_index", name="uq_task_submissions_task_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questionnaire_tasks.id", ondelete="CASCADE"), nullable=False
    )

    submit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    generated_answers: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    proxy_host: Mapped[Optional[str]] = mapped_column(String(255))
    proxy_port: Mapped[Optional[int]] = mapped_column(Integer)
    proxy_requested_area: Mapped[Optional[str]] = mapped_column(String(64))
    proxy_reported_location: Mapped[Optional[str]] = mapped_column(String(128))
    proxy_city_code: Mapped[Optional[str]] = mapped_column(String(32))
    proxy_carrier: Mapped[Optional[str]] = mapped_column(String(32))
    proxy_exit_ip: Mapped[Optional[str]] = mapped_column(String(64))
    proxy_remaining_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    proxy_latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    proxy_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    failure_stage: Mapped[Optional[str]] = mapped_column(String(32))

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["QuestionnaireTask"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"TaskSubmission(id={self.id}, task_id={self.task_id}, index={self.submit_index})"


class TaskTextAnswerPool(Base):
    """一个任务中某道单行或多行文本题按提交序号排列的持久化答案池。"""

    __tablename__ = "task_text_answer_pools"
    __table_args__ = (
        UniqueConstraint("task_id", "question_id", name="uq_task_text_pool_question"),
        CheckConstraint(
            "jsonb_typeof(answers) = 'array'", name="ck_task_text_pool_answers_array"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questionnaire_tasks.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(128), nullable=False)
    question_label: Mapped[str] = mapped_column(Text, nullable=False)
    answers: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["QuestionnaireTask"] = relationship(back_populates="text_answer_pools")


class TaskProportionAnswerPlan(Base):
    """比例模式预先计算的每份问卷选择类题目答案。"""

    __tablename__ = "task_proportion_answer_plans"
    __table_args__ = (
        UniqueConstraint("task_id", "submit_index", name="uq_task_proportion_plan_index"),
        CheckConstraint(
            "jsonb_typeof(answers) = 'object'", name="ck_task_proportion_plan_answers_object"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questionnaire_tasks.id", ondelete="CASCADE"), nullable=False
    )
    submit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["QuestionnaireTask"] = relationship(back_populates="proportion_answer_plans")
