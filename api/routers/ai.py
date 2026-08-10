"""
AI configuration routing module

Provides AI settings management and connectivity testing APIs.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AIConfigRequest, AIConfigResponse, AITestResponse, DataResponse
from ai import ai_config_manager
from ai.client import AIClient
from db.session import get_session


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/config", response_model=DataResponse)
async def get_ai_config(session: AsyncSession = Depends(get_session)):
    """
    Get current AI configuration

    Returns current AI settings without exposing the API key.
    """
    try:
        config = await ai_config_manager.get_config(session)

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
async def update_ai_config(
    request: AIConfigRequest, session: AsyncSession = Depends(get_session)
):
    """
    Update AI configuration

    Update one or more AI settings. Only provided fields are updated.

    Args:
        request: Configuration update request

    Returns:
        Updated configuration (without API key)
    """
    try:
        await ai_config_manager.update_config(
            session,
            api_key=request.api_key,
            model=request.model,
            base_url=request.base_url,
            enabled=request.enabled
        )

        config = await ai_config_manager.get_config(session)

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
async def test_ai_connection(session: AsyncSession = Depends(get_session)):
    """
    Test AI API connection and authentication

    Sends a simple test message to verify API key and connectivity.

    Returns:
        Test result
    """
    try:
        if not await ai_config_manager.is_configured(session):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI is not configured. Please set API key and enable AI first."
            )

        config = await ai_config_manager.get_config(session)
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
