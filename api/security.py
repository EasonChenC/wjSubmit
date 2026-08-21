"""Password, JWT, CSRF and token helpers."""
import hashlib, hmac, os, re, secrets
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
import jwt
from fastapi import HTTPException, Request, status

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = "HS256"
ACCESS_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
REFRESH_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "7"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COMMON = {"password", "password123", "12345678", "qwerty123", "admin123"}

def _secret():
    if len(JWT_SECRET) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return JWT_SECRET

def validate_password(password: str, username: str = ""):
    if not 12 <= len(password) <= 128: raise ValueError("密码长度必须为12到128位")
    if username and password.casefold() == username.casefold(): raise ValueError("密码不能与用户名相同")
    if password.casefold() in COMMON: raise ValueError("密码过于常见")
    if not all(re.search(p, password) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^\w\s]")):
        raise ValueError("密码须包含大小写字母、数字和特殊字符")

def hash_password(password): return _hasher.hash(password)
def verify_password(password, encoded):
    try: return _hasher.verify(encoded, password)
    except Exception: return False

def create_access_token(user_id):
    now=datetime.now(timezone.utc)
    return jwt.encode({"sub":str(user_id),"type":"access","iat":now,"exp":now+timedelta(minutes=ACCESS_MINUTES)},_secret(),algorithm=JWT_ALGORITHM)
def create_refresh_token(user_id):
    now=datetime.now(timezone.utc); jti=secrets.token_urlsafe(32)
    return jwt.encode({"sub":str(user_id),"type":"refresh","jti":jti,"iat":now,"exp":now+timedelta(days=REFRESH_DAYS)},_secret(),algorithm=JWT_ALGORITHM)
def decode_token(token, expected):
    try: p=jwt.decode(token,_secret(),algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError: raise HTTPException(status_code=401,detail="Authentication required")
    if p.get("type") != expected or not p.get("sub"): raise HTTPException(status_code=401,detail="Authentication required")
    return p
def token_hash(token): return hashlib.sha256(token.encode()).hexdigest()
def csrf_token(): return secrets.token_urlsafe(32)
def set_auth_cookies(response, access, refresh, csrf):
    response.set_cookie("access_token",access,httponly=True,secure=COOKIE_SECURE,samesite="lax",max_age=ACCESS_MINUTES*60,path="/")
    response.set_cookie("refresh_token",refresh,httponly=True,secure=COOKIE_SECURE,samesite="lax",max_age=REFRESH_DAYS*86400,path="/api/auth")
    response.set_cookie("csrf_token",csrf,httponly=False,secure=COOKIE_SECURE,samesite="lax",max_age=REFRESH_DAYS*86400,path="/")
def clear_auth_cookies(response):
    for n in ("access_token","refresh_token","csrf_token"): response.delete_cookie(n,path="/api/auth" if n=="refresh_token" else "/")
def require_csrf(request: Request):
    if request.method in {"GET","HEAD","OPTIONS"}: return
    supplied=request.headers.get("X-CSRF-Token"); cookie=request.cookies.get("csrf_token")
    if not supplied or not cookie or not hmac.compare_digest(supplied,cookie): raise HTTPException(status_code=403,detail="Invalid CSRF token")
