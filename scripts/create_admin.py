import asyncio, os, getpass
from sqlalchemy import select
from db.session import init_engine, close_engine, get_session
from db.models import User, Role
from api.security import hash_password, validate_password
async def main():
    username=os.getenv("INITIAL_ADMIN_USERNAME") or input("Username: ")
    password=os.getenv("INITIAL_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    validate_password(password, username); init_engine()
    try:
        async for s in get_session():
            role=await s.scalar(select(Role).where(Role.code=="admin"))
            if not role: raise RuntimeError("admin role missing; run SQL migrations")
            u=await s.scalar(select(User).where(User.username==username))
            if u: raise RuntimeError("user already exists")
            s.add(User(username=username,password_hash=hash_password(password),role_id=role.id))
            try:
                await s.commit()
            except Exception:
                await s.rollback()
                raise
            print("admin created")
    finally:
        await close_engine()
if __name__=="__main__": asyncio.run(main())
