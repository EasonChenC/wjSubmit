"""
AI configuration routing module

Provides AI settings management and connectivity testing APIs.
"""

from fastapi import APIRouter, HTTPException, status

from ..models import AIConfigRequest, AIConfigResponse, AITestResponse, DataResponse
from ai.config import AIConfigManager
from ai.client import AIClient


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/config", response_model=DataResponse)
async def get_ai_config():
    """
    Get current AI configuration

    Returns current AI settings without exposing the API key.
    """
    try:
        manager = AIConfigManager.get_instance()
        config = manager.get_config()

        response_data = AIConfigResponse(
            model=config.model,
            base_url=config.base_url,
            enabled=config.enabled,
            has_api_key=bool(config.api_key.strip())
        )

        return DataResponse(
            success=True,
            message="AI configuration retrieved successfully",
            data=response_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve AI configuration: {str(e)}"
        )


@router.post("/config", response_model=DataResponse)
async def update_ai_config(request: AIConfigRequest):
    """
    Update AI configuration

    Update one or more AI settings. Only provided fields are updated.

    Args:
        request: Configuration update request

    Returns:
        Updated configuration (without API key)
    """
    try:
        manager = AIConfigManager.get_instance()

        # Update configuration with provided values
        manager.update_config(
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
            enabled=request.enabled
        )

        config = manager.get_config()

        response_data = AIConfigResponse(
            model=config.model,
            base_url=config.base_url,
            enabled=config.enabled,
            has_api_key=bool(config.api_key.strip())
        )

        return DataResponse(
            success=True,
            message="AI configuration updated successfully",
            data=response_data
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AI configuration: {str(e)}"
        )


@router.post("/test", response_model=DataResponse)
async def test_ai_connection():
    """
    Test AI API connection and authentication

    Sends a simple test message to verify API key and connectivity.

    Returns:
        Test result
    """
    try:
        manager = AIConfigManager.get_instance()

        if not manager.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI is not configured. Please set API key and enable AI first."
            )

        config = manager.get_config()
        client = AIClient(config.api_key, config.model, config.base_url)

        success = await client.test_connection()

        if success:
            response_data = AITestResponse(
                success=True,
                message="AI connection test passed successfully"
            )
            return DataResponse(
                success=True,
                message="Connection test successful",
                data=response_data
            )
        else:
            response_data = AITestResponse(
                success=False,
                message="AI connection test failed"
            )
            return DataResponse(
                success=False,
                message="Connection test failed",
                data=response_data
            )

    except HTTPException:
        raise
    except Exception as e:
        response_data = AITestResponse(
            success=False,
            message=str(e)
        )
        return DataResponse(
            success=False,
            message=f"Connection test failed: {str(e)}",
            data=response_data
        )
