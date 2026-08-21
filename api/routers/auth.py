from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import get_session
from db.models import User, Role, UserSession, LoginAttempt, AuditLog
from api.dependencies import get_current_user
from api.security import *

router=APIRouter(prefix="/api/auth",tags=["auth"])
class LoginIn(BaseModel): username:str=Field(min_length=1,max_length=64); password:str
class PasswordIn(BaseModel): current_password:str; new_password:str

def public_user(u): return {"id":str(u.id),"username":u.username,"email":u.email,"role":u.role.code if u.role else None}
async def audit(session,user,action,request):
    session.add(AuditLog(user_id=user.id if user else None,action=action,ip_address=request.client.host if request.client else None,user_agent=request.headers.get("user-agent"),metadata_json={}))

@router.post("/login")
async def login(data:LoginIn, request:Request, response:Response, session:AsyncSession=Depends(get_session)):
    user=await session.scalar(select(User).options(selectinload(User.role)).where(User.username==data.username))
    ok=bool(user and verify_password(data.password,user.password_hash) and user.is_active and not user.deleted_at)
    session.add(LoginAttempt(username=data.username,ip_address=request.client.host if request.client else None,success=ok,reason=None if ok else "invalid_credentials"))
    if not ok:
        if user:
            user.failed_login_count=(user.failed_login_count or 0)+1
            if user.failed_login_count>=5:
                user.is_locked=True; user.locked_until=datetime.now(timezone.utc)+timedelta(minutes=5)
        await session.commit(); raise HTTPException(401,"用户名或密码错误")
    user.failed_login_count=0; user.is_locked=False; user.locked_until=None; user.last_login_at=datetime.now(timezone.utc); user.last_login_ip=request.client.host if request.client else None
    access=create_access_token(user.id); refresh=create_refresh_token(user.id)
    session.add(UserSession(user_id=user.id,refresh_token_hash=token_hash(refresh),expires_at=datetime.now(timezone.utc)+timedelta(days=REFRESH_DAYS),ip_address=request.client.host if request.client else None,user_agent=request.headers.get("user-agent")))
    await audit(session,user,"auth.login",request); await session.commit(); set_auth_cookies(response,access,refresh,csrf_token())
    return {"success":True,"data":{"user":public_user(user),"token":access}}

@router.get("/me")
async def me(user:User=Depends(get_current_user)): return {"success":True,"data":public_user(user)}

@router.post("/refresh")
async def refresh(request:Request,response:Response,session:AsyncSession=Depends(get_session)):
    raw=request.cookies.get("refresh_token")
    if not raw: raise HTTPException(401,"Authentication required")
    p=decode_token(raw,"refresh"); s=await session.scalar(select(UserSession).where(UserSession.refresh_token_hash==token_hash(raw),UserSession.revoked_at.is_(None)))
    if not s or s.expires_at<datetime.now(timezone.utc): raise HTTPException(401,"Authentication required")
    user=await session.get(User,s.user_id)
    if not user or not user.is_active or user.deleted_at: raise HTTPException(401,"Authentication required")
    s.revoked_at=datetime.now(timezone.utc); new=create_refresh_token(user.id); session.add(UserSession(user_id=user.id,refresh_token_hash=token_hash(new),expires_at=datetime.now(timezone.utc)+timedelta(days=REFRESH_DAYS)))
    await session.commit(); set_auth_cookies(response,create_access_token(user.id),new,csrf_token()); return {"success":True,"data":{"user":public_user(user)}}

@router.post("/logout")
async def logout(request:Request,response:Response,session:AsyncSession=Depends(get_session)):
    raw=request.cookies.get("refresh_token")
    if raw:
        s=await session.scalar(select(UserSession).where(UserSession.refresh_token_hash==token_hash(raw))); 
        if s: s.revoked_at=datetime.now(timezone.utc); await session.commit()
    clear_auth_cookies(response); return {"success":True}

@router.post("/logout-all")
async def logout_all(response:Response,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_session)):
    await session.execute(update(UserSession).where(UserSession.user_id==user.id,UserSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc))); await session.commit(); clear_auth_cookies(response); return {"success":True}

@router.post("/change-password")
async def change_password(data:PasswordIn,user:User=Depends(get_current_user),session:AsyncSession=Depends(get_session)):
    if not verify_password(data.current_password,user.password_hash): raise HTTPException(400,"当前密码错误")
    try: validate_password(data.new_password,user.username)
    except ValueError as e: raise HTTPException(422,str(e))
    user.password_hash=hash_password(data.new_password); user.password_changed_at=datetime.now(timezone.utc)
    await session.execute(update(UserSession).where(UserSession.user_id==user.id).values(revoked_at=datetime.now(timezone.utc))); await session.commit(); return {"success":True}
