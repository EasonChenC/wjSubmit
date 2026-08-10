# db/session.py
"""
数据库连接层（SQLAlchemy 2.0 Async ORM）

连接串从环境变量 DATABASE_URL 读取（见 .env / .env.example），
底层驱动为 asyncpg。
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker] = None


def init_engine() -> AsyncEngine:
    """创建全局 Engine + Session工厂（应用启动时调用一次）"""
    global _engine, _session_factory

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill in "
            "your PostgreSQL connection string."
        )

    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,   # 连接失效自动重连（数据库重启/网络抖动）
            pool_recycle=1800,    # 30分钟回收空闲连接
            echo=False,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    return _engine


async def close_engine() -> None:
    """关闭全局 Engine（应用关闭时调用）"""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_engine() -> AsyncEngine:
    """获取已初始化的 Engine"""
    if _engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")
    return _engine


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖注入：获取一个请求级别的 AsyncSession

    Usage:
        @router.get("/tasks")
        async def list_tasks(session: AsyncSession = Depends(get_session)):
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")

    async with _session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """独立于 FastAPI 请求生命周期的 Session 上下文管理器

    用于 BackgroundTasks 等脱离请求作用域的代码（不能使用 Depends）。

    Usage:
        async with session_scope() as session:
            ...
    """
    if _session_factory is None:
        raise RuntimeError("Database engine is not initialized. Call init_engine() first.")

    async with _session_factory() as session:
        yield session


async def check_connection() -> bool:
    """连通性检查，供健康检查接口使用"""
    from sqlalchemy import text

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
