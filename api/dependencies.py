# api/dependencies.py
"""
API依赖注入

提供通用的依赖函数。
"""

from typing import Optional
from fastapi import Header, HTTPException, status


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    """
    验证API密钥（可选）

    生产环境可启用此功能进行API访问控制。

    Args:
        x_api_key: HTTP Header中的API密钥

    Returns:
        验证是否通过

    Raises:
        HTTPException: 密钥无效时抛出401异常
    """
    # 开发环境：跳过验证
    # 生产环境：取消注释下面的代码

    # VALID_API_KEYS = ["your-secret-key-here"]
    # if x_api_key not in VALID_API_KEYS:
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Invalid API Key"
    #     )

    return True
