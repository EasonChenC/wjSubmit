"""AI configuration management module

Manages global AI settings (API key, model, base URL) backed by the
`ai_configs` table (see sql/002_ai_configs.sql, db/models.py::AIConfigModel).

Currently the project runs in single-user mode: all reads/writes target the
one row where user_id IS NULL (the "global" config). Once authentication is
introduced, pass a user_id through to scope configs per user.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import AIConfigModel


@dataclass
class AIConfig:
    """AI configuration (plain data, detached from the DB row)"""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    enabled: bool = False


class AIConfigManager:
    """Loads/persists AI configuration from the database.

    Replaces the previous in-memory singleton. All methods are async and
    take an AsyncSession (see db.session.get_session) so callers control
    the transaction boundary.
    """

    async def _get_or_create_row(self, session: AsyncSession) -> AIConfigModel:
        """Get the global config row (user_id IS NULL), creating it if absent"""
        result = await session.execute(
            select(AIConfigModel).where(AIConfigModel.user_id.is_(None))
        )
        row = result.scalar_one_or_none()

        if row is None:
            row = AIConfigModel()
            session.add(row)
            await session.commit()

        return row

    async def get_config(self, session: AsyncSession) -> AIConfig:
        """Get current configuration"""
        row = await self._get_or_create_row(session)
        return AIConfig(
            api_key=row.api_key,
            model=row.model,
            base_url=row.base_url,
            enabled=row.enabled,
        )

    async def update_config(
        self,
        session: AsyncSession,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Update configuration (only non-None values are updated)"""
        row = await self._get_or_create_row(session)

        if api_key is not None:
            row.api_key = api_key
        if model is not None:
            row.model = model
        if base_url is not None:
            row.base_url = base_url
        if enabled is not None:
            row.enabled = enabled

        await session.commit()

    async def is_configured(self, session: AsyncSession) -> bool:
        """Check if AI is fully configured and enabled"""
        config = await self.get_config(session)
        return bool(config.api_key.strip()) and config.enabled
