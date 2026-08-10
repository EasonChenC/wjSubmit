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
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    role: Mapped["Role"] = relationship(back_populates="users")
    ai_configs: Mapped[list["AIConfigModel"]] = relationship(back_populates="user")
    questionnaire_tasks: Mapped[list["QuestionnaireTask"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"User(id={self.id}, username={self.username!r})"


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
            "detection_method IN ('keyword', 'ai')", name="ck_questionnaire_tasks_detection_method"
        ),
        CheckConstraint(
            "submit_mode IN ('random', 'high_reliability')", name="ck_questionnaire_tasks_submit_mode"
        ),
        CheckConstraint(
            "attitude IN ('positive', 'negative')", name="ck_questionnaire_tasks_attitude"
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_questionnaire_tasks_status",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_questionnaire_tasks_progress"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    url: Mapped[str] = mapped_column(String(500), nullable=False)
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

    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    total_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    submitted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="questionnaire_tasks")
    submissions: Mapped[list["TaskSubmission"]] = relationship(
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

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped["QuestionnaireTask"] = relationship(back_populates="submissions")

    def __repr__(self) -> str:
        return f"TaskSubmission(id={self.id}, task_id={self.task_id}, index={self.submit_index})"
