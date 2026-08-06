"""AI configuration management module

Manages global AI settings (API key, model, base URL) in memory.
Supports OpenAI-compatible APIs and third-party proxies.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AIConfig:
    """AI configuration"""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    enabled: bool = False


class AIConfigManager:
    """Singleton manager for AI configuration (in-memory storage)"""

    _instance: Optional['AIConfigManager'] = None
    _config: AIConfig

    def __new__(cls) -> 'AIConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = AIConfig()
        return cls._instance

    @classmethod
    def get_instance(cls) -> 'AIConfigManager':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_config(self) -> AIConfig:
        """Get current configuration"""
        return self._config

    def update_config(self,
                     api_key: Optional[str] = None,
                     model: Optional[str] = None,
                     base_url: Optional[str] = None,
                     enabled: Optional[bool] = None) -> None:
        """Update configuration (only non-None values are updated)"""
        if api_key is not None:
            self._config.api_key = api_key
        if model is not None:
            self._config.model = model
        if base_url is not None:
            self._config.base_url = base_url
        if enabled is not None:
            self._config.enabled = enabled

    def is_configured(self) -> bool:
        """Check if AI is fully configured and enabled"""
        return bool(self._config.api_key.strip()) and self._config.enabled

    def reset(self) -> None:
        """Reset to default configuration"""
        self._config = AIConfig()
