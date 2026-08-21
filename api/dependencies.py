from datetime import datetime, timezone
from uuid import UUID
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session
from db.models import User
from .security import decode_token

async def get_current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User:
    token = request.cookies.get("access_token") or (request.headers.get("Authorization", "").removeprefix("Bearer ").strip())
    if not token: raise HTTPException(401, "Authentication required")
    payload = decode_token(token, "access")
    try: uid = UUID(payload["sub"])
    except (ValueError, KeyError): raise HTTPException(401, "Authentication required")
    user = await session.scalar(select(User).options(selectinload(User.role)).where(User.id == uid))
    now = datetime.now(timezone.utc)
    if not user or not user.is_active or user.deleted_at is not None or (user.is_locked and (not user.locked_until or user.locked_until > now)):
        raise HTTPException(401, "Authentication required")
    return user

def require_roles(*roles: str):
    async def dep(user: User = Depends(get_current_user)) -> User:
        if not user.role or user.role.code not in roles: raise HTTPException(403, "Permission denied")
        return user
    return dep

async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    return True
