"""AI module for questionnaire analysis"""

from .config import AIConfig, AIConfigManager
from .client import AIClient
from .reverse_detector import override_schema_with_ai_detection

# Module-level instance: AIConfigManager itself holds no state now (config
# lives in the database), so a plain instance can be shared across requests.
ai_config_manager = AIConfigManager()

__all__ = [
    'AIConfig',
    'AIConfigManager',
    'AIClient',
    'override_schema_with_ai_detection',
    'ai_config_manager',
]
