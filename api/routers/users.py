from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from db.session import get_session
from db.models import User, Role, UserSession, AuditLog
from api.dependencies import require_roles
from api.security import hash_password, validate_password

router=APIRouter(prefix="/api/users",tags=["users"])
class UserCreate(BaseModel): username:str=Field(min_length=1,max_length=64); password:str; email:str|None=None; role:str="viewer"
class UserPatch(BaseModel): email:str|None=None; role:str|None=None; is_active:bool|None=None
class ResetPassword(BaseModel): password:str
def out(u): return {"id":str(u.id),"username":u.username,"email":u.email,"role":u.role.code if u.role else None,"is_active":u.is_active,"is_locked":u.is_locked,"created_at":u.created_at.isoformat() if u.created_at else None,"last_login_at":u.last_login_at.isoformat() if u.last_login_at else None}
async def log(s,u,a,rid=None): s.add(AuditLog(user_id=u.id,action=a,resource_type="user",resource_id=str(rid or u.id),metadata_json={}))

@router.get("")
async def list_users(user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session),q:str|None=None,role:str|None=None,status:str|None=None,offset:int=0,limit:int=20):
    filters=[User.deleted_at.is_(None)]
    if q: filters.append((User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    if role: filters.append(Role.code==role)
    if status=="active": filters.append(User.is_active.is_(True))
    elif status=="disabled": filters.append(User.is_active.is_(False))
    total=await session.scalar(select(func.count(User.id)).join(Role).where(*filters))
    stmt=select(User).options(selectinload(User.role)).join(Role).where(*filters).order_by(User.created_at.desc()).offset(max(offset,0)).limit(min(max(limit,1),100))
    rows=(await session.scalars(stmt)).all(); return {"success":True,"data":{"items":[out(x) for x in rows],"total":total or 0}}
@router.post("")
async def create(data:UserCreate,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    try: validate_password(data.password,data.username)
    except ValueError as e: raise HTTPException(422,str(e))
    role=await session.scalar(select(Role).where(Role.code==data.role));
    if not role: raise HTTPException(422,"invalid role")
    if await session.scalar(select(User).where(User.username==data.username)): raise HTTPException(409,"username already exists")
    u=User(username=data.username,email=data.email,password_hash=hash_password(data.password),role_id=role.id); u.role=role; session.add(u); await session.flush(); await log(session,user,"user.create",u.id); await session.commit(); await session.refresh(u); return {"success":True,"data":out(u)}
@router.get("/{uid}")
async def get(uid:UUID,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    return {"success":True,"data":out(u)}
@router.patch("/{uid}")
async def patch(uid:UUID,data:UserPatch,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    if data.is_active is False and uid==user.id: raise HTTPException(400,"cannot disable self")
    if data.role:
        role=await session.scalar(select(Role).where(Role.code==data.role));
        if not role: raise HTTPException(422,"invalid role")
        u.role_id=role.id
    if data.email is not None:u.email=data.email
    if data.is_active is not None:
        u.is_active=data.is_active
        if not data.is_active: await session.execute(update(UserSession).where(UserSession.user_id==uid,UserSession.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    await log(session,user,"user.update",uid); await session.commit(); await session.refresh(u); return {"success":True,"data":out(u)}
@router.post("/{uid}/enable")
async def enable(uid:UUID,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    u.is_active=True; u.is_locked=False; u.locked_until=None; await log(session,user,"user.enable",uid); await session.commit(); return {"success":True}
@router.post("/{uid}/disable")
async def disable(uid:UUID,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    if uid==user.id: raise HTTPException(400,"cannot disable self")
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    u.is_active=False; await session.execute(update(UserSession).where(UserSession.user_id==uid).values(revoked_at=datetime.now(timezone.utc))); await log(session,user,"user.disable",uid); await session.commit(); return {"success":True}
@router.post("/{uid}/reset-password")
async def reset(uid:UUID,data:ResetPassword,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    try: validate_password(data.password,u.username)
    except ValueError as e: raise HTTPException(422,str(e))
    u.password_hash=hash_password(data.password); await session.execute(update(UserSession).where(UserSession.user_id==uid).values(revoked_at=datetime.now(timezone.utc))); await log(session,user,"user.reset_password",uid); await session.commit(); return {"success":True}
@router.delete("/{uid}")
async def delete(uid:UUID,user:User=Depends(require_roles("admin")),session:AsyncSession=Depends(get_session)):
    if uid==user.id: raise HTTPException(400,"cannot delete self")
    u=await session.scalar(select(User).options(selectinload(User.role)).where(User.id==uid))
    if not u: raise HTTPException(404,"Not found")
    u.deleted_at=datetime.now(timezone.utc); u.is_active=False; await session.execute(update(UserSession).where(UserSession.user_id==uid).values(revoked_at=datetime.now(timezone.utc))); await log(session,user,"user.delete",uid); await session.commit(); return {"success":True}

