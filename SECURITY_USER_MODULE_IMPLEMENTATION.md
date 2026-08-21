# 用户管理与统一认证模块技术实现方案

## 1. 文档目的

本文档用于指导当前问卷自动化系统增加用户管理、登录认证、角色权限和安全防护能力。目标是：

1. 未登录用户不能访问业务页面和业务接口；
2. 登录用户只能访问自己有权限的资源；
3. 管理员可以创建、查看、编辑、启用、禁用和删除用户；
4. 所有高风险操作可审计、可追踪、可撤销；
5. 对暴力破解、越权、CSRF、XSS、SSRF、资源耗尽和敏感信息泄露进行防护。

---

## 2. 当前项目现状与必须修复的问题

### 2.1 已有基础

当前项目已经存在以下基础结构：

```text
db/models.py
  Role
  User

sql/001_roles.sql
sql/001_users.sql

frontend/src/views/Login/index.vue
frontend/src/api/auth.ts
frontend/src/stores/user.ts
frontend/src/utils/storage.ts
frontend/src/router/index.ts
```

### 2.2 当前安全缺口

1. 后端尚未实现真正的 `/api/auth/login`、`/api/auth/me` 和会话校验；
2. `api/dependencies.py` 中的 `verify_api_key()` 当前直接返回 `True`；
3. 问卷和 AI 路由没有统一认证依赖；
4. 前端 `user.ts` 存在 `local-demo-token` 回退逻辑，任何非空用户名和密码都可能进入本地演示状态；
5. CORS 使用 `allow_origins=["*"]` 且允许凭据，生产环境不安全；
6. 任务和 AI 配置需要补充用户归属校验，防止通过任务 ID 越权访问；
7. 尚无会话撤销、登录失败限速、审计日志和安全事件记录。

这些问题必须在启用用户模块前修复。

---

## 3. 总体架构

```text
浏览器
  │
  ├─ Vue Router：页面体验层拦截
  ├─ Axios：自动携带会话、处理 401/403
  │
  ▼
FastAPI
  ├─ /api/auth/*       登录、刷新、注销、当前用户
  ├─ /api/users/*      管理员用户管理
  ├─ /api/questionnaire/*  登录 + 角色 + 资源归属
  ├─ /api/ai/*         登录 + 配置归属
  └─ 安全中间件：CORS、请求头、限速、审计
  │
  ▼
PostgreSQL
  ├─ users
  ├─ roles
  ├─ user_sessions
  ├─ login_attempts
  ├─ audit_logs
  └─ questionnaire_tasks.user_id
```

认证采用短期 Access Token 加 Refresh Token。推荐生产环境使用 HttpOnly Cookie 保存 Refresh Token，避免 JavaScript 直接读取长期凭证。

---

## 4. 角色与权限设计

### 4.1 角色

| 角色编码 | 名称 | 权限范围 |
|---|---|---|
| `admin` | 管理员 | 用户、角色、系统设置、AI设置、全部任务和审计日志 |
| `operator` | 操作员 | 创建、查看、取消和管理自己的问卷任务 |
| `viewer` | 查看者 | 只读查看被授权的任务和结果 |

不建议在业务代码中大量写死角色判断，推荐使用权限码。

### 4.2 权限码

```text
user:create
user:read
user:update
user:disable
user:delete
task:create
task:read
task:update
task:cancel
task:delete
ai:read
ai:update
audit:read
system:settings
```

### 4.3 权限校验原则

```text
前端隐藏按钮 = 用户体验控制
后端权限依赖 = 安全边界
数据库资源归属 = 防止越权
```

不能将 UUID、前端路由、按钮隐藏或 localStorage 标记当作权限控制。

---

## 5. 数据库设计

## 5.1 users 表扩展

在现有 `users` 表基础上增加：

```sql
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS failed_login_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS locked_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_login_ip INET,
    ADD COLUMN IF NOT EXISTS password_changed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
```

建议使用软删除：删除用户时设置 `deleted_at`、`is_active=false`，不要直接物理删除审计记录和任务关联。

## 5.2 user_sessions 表

```sql
CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(128) NOT NULL UNIQUE,
    user_agent TEXT,
    ip_address INET,
    expires_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id
    ON user_sessions(user_id);
```

数据库只保存 Refresh Token 哈希，不保存原始 Token。

## 5.3 login_attempts 表

```sql
CREATE TABLE IF NOT EXISTS login_attempts (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(64),
    ip_address INET,
    success BOOLEAN NOT NULL,
    reason VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_username_time
    ON login_attempts(username, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_time
    ON login_attempts(ip_address, created_at DESC);
```

## 5.4 audit_logs 表

```sql
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(128),
    ip_address INET,
    user_agent TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
    ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id
    ON audit_logs(user_id);
```

## 5.5 任务归属

创建任务时写入当前用户：

```python
task_row.user_id = current_user.id
```

历史任务迁移策略：

```sql
UPDATE questionnaire_tasks
SET user_id = '<管理员用户UUID>'
WHERE user_id IS NULL;
```

确认历史数据归属后，再执行：

```sql
ALTER TABLE questionnaire_tasks
    ALTER COLUMN user_id SET NOT NULL;
```

---

## 6. 密码安全

### 6.1 哈希算法

使用 Argon2id；禁止自行实现哈希算法，禁止 MD5、SHA1、裸 SHA256 和可逆加密。

示例依赖：

```text
argon2-cffi
```

示例代码：

```python
from argon2 import PasswordHasher

password_hasher = PasswordHasher()

def hash_password(password: str) -> str:
    return password_hasher.hash(password)

def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        return password_hasher.verify(encoded_hash, password)
    except Exception:
        return False
```

### 6.2 密码策略

```text
最少12位
最多128位
禁止为空白
禁止使用用户名作为密码
禁止常见弱密码
创建用户和重置密码时均校验
```

密码、密码哈希和 Token 不得出现在 API 响应、日志、异常信息和审计 metadata 中。

---

## 7. 认证接口

### 7.1 登录

```http
POST /api/auth/login
Content-Type: application/json
```

请求：

```json
{
  "username": "operator1",
  "password": "强密码"
}
```

成功响应只返回用户基本信息：

```json
{
  "success": true,
  "data": {
    "user": {
      "id": "UUID",
      "username": "operator1",
      "role": "operator"
    }
  }
}
```

认证凭证通过 Cookie 设置：

```text
access_token：短期，建议15～30分钟
refresh_token：HttpOnly，建议7～30天
```

失败时统一返回：

```text
用户名或密码错误
```

不得区分“用户不存在”和“密码错误”。

### 7.2 其他认证接口

```text
GET  /api/auth/me
POST /api/auth/refresh
POST /api/auth/logout
POST /api/auth/logout-all
POST /api/auth/change-password
```

Refresh Token 轮换流程：

```text
读取 Cookie
→ 校验签名和有效期
→ 对 Token 哈希后查询 user_sessions
→ 检查 revoked_at、expires_at 和用户状态
→ 撤销旧会话
→ 生成新 Refresh Token 并写入数据库
```

---

## 8. FastAPI 统一鉴权

### 8.1 当前用户依赖

建议在 `api/dependencies.py` 新增：

```python
async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> User:
    token = read_access_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    user = await session.get(User, user_id)

    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Authentication required")

    if user.is_locked and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Authentication required")

    return user
```

### 8.2 角色依赖

```python
def require_roles(*allowed_roles: str):
    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.code not in allowed_roles:
            raise HTTPException(status_code=403, detail="Permission denied")
        return user
    return dependency
```

### 8.3 路由保护矩阵

| 路由 | 未登录 | operator | viewer | admin |
|---|---:|---:|---:|---:|
| `/api/auth/login` | 允许 | 允许 | 允许 | 允许 |
| `/api/questionnaire/*` | 401 | 按资源权限 | 只读 | 全部 |
| `/api/ai/config` | 401 | 自己配置 | 只读或禁止 | 全部 |
| `/api/users/*` | 401 | 403 | 403 | 允许 |
| `/api/audit-logs` | 401 | 403 | 403 | 允许 |

问卷和 AI 路由全部增加 `Depends(get_current_user)`；用户管理和审计路由增加 `Depends(require_roles("admin"))`。

---

## 9. 资源归属与越权防护

### 9.1 任务查询

普通用户必须使用带归属条件的查询：

```python
task = await session.scalar(
    select(QuestionnaireTask).where(
        QuestionnaireTask.id == task_id,
        QuestionnaireTask.user_id == current_user.id,
    )
)
```

管理员可以使用不带用户条件的查询，但必须经过角色依赖。

### 9.2 操作权限

```text
创建任务：task:create
查看任务：task:read + 资源归属
取消任务：task:cancel + 资源归属
删除任务：task:delete + 资源归属
```

对不存在资源和无权资源可以统一返回 404，减少资源枚举信息泄露。

### 9.3 AI 配置

普通用户只能读写自己的 AI 配置。API Key 只能返回掩码，例如：

```text
sk-****abcd
```

真正的 API Key 只在后端调用 AI 时读取。

---

## 10. 用户管理 API

```text
POST   /api/users                  创建用户
GET    /api/users                  分页、搜索、筛选用户
GET    /api/users/{id}             查看详情
PATCH  /api/users/{id}             编辑邮箱、角色、状态
POST   /api/users/{id}/enable      启用
POST   /api/users/{id}/disable     禁用并撤销会话
POST   /api/users/{id}/reset-password  管理员重置密码
DELETE /api/users/{id}             软删除
```

安全规则：

1. 仅管理员可调用；
2. 不允许删除自己；
3. 不允许删除最后一个启用的管理员；
4. 禁用用户时撤销该用户全部 Refresh Token；
5. 删除用户时保留审计记录；
6. 密码重置使用独立接口，不能通过普通编辑接口修改；
7. 所有操作写入 `audit_logs`。

---

## 11. 前端实现

### 11.1 删除本地演示回退

必须删除：

```typescript
this.token = 'local-demo-token'
```

登录失败只能返回失败，不能自动创建本地登录状态。

### 11.2 路由守卫

```typescript
router.beforeEach(async (to) => {
  const userStore = useUserStore()

  if (to.meta.auth && !userStore.isLoggedIn) {
    return '/login'
  }

  if (to.meta.role && userStore.role !== to.meta.role) {
    return '/403'
  }
})
```

路由守卫只负责体验；后端仍必须对每个请求再次验证。

### 11.3 Axios 处理

```typescript
request.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      userStore.clearSession()
      router.replace('/login')
    }
    if (error.response?.status === 403) {
      router.replace('/403')
    }
    return Promise.reject(error)
  }
)
```

### 11.4 用户管理页面

新增：

```text
frontend/src/views/Admin/Users.vue
frontend/src/api/users.ts
```

页面功能：

```text
用户列表、分页、关键字搜索
创建用户
编辑用户
角色选择
启用/禁用
重置密码
软删除
```

管理员菜单和页面按钮可以隐藏，但后端权限才是最终判断。

---

## 12. CORS、CSRF 和安全响应头

### 12.1 CORS

当前的：

```python
allow_origins=["*"]
allow_credentials=True
```

必须改为明确来源：

```python
allow_origins=[
    "http://localhost:5173",
    "https://frontend.example.com",
]
allow_credentials=True
allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"]
```

### 12.2 CSRF

当认证使用 Cookie 时，所有写请求都执行：

1. 校验 `Origin` 或 `Referer`；
2. 校验 `X-CSRF-Token`；
3. Cookie 设置 `SameSite=Lax` 或 `Strict`；
4. 删除、修改密码和用户管理操作要求重新认证或二次确认。

### 12.3 安全响应头

建议通过反向代理或 FastAPI 中间件设置：

```text
Content-Security-Policy
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy
Strict-Transport-Security（仅 HTTPS）
```

---

## 13. 恶意攻击防护

### 13.1 登录暴力破解

按 IP、用户名和 IP+用户名组合限速：

```text
单 IP 每分钟最多20次登录
同一账号连续5次失败，锁定5分钟
连续10次失败，锁定30分钟
```

失败响应统一为“用户名或密码错误”。

### 13.2 SSRF

问卷 URL 必须：

```text
只允许 http/https
禁止 localhost、回环地址、内网 CIDR、云元数据地址
DNS 解析后再次检查 IP
禁止 file://、ftp:// 等协议
设置请求超时、响应大小和重定向次数
```

### 13.3 资源耗尽

限制：

```text
单用户并发任务数
单任务最大提交数
浏览器上下文数量
AI 调用频率
代理获取频率
请求体大小
```

### 13.4 日志脱敏

禁止记录：

```text
密码、密码哈希、Authorization、Cookie、Refresh Token、AI Key、代理账号密码
```

异常响应不返回 Python 堆栈、SQL 语句和供应商凭据。

---

## 14. 初始化管理员

不要在代码中写默认管理员密码。建议新增一次性命令：

```bash
python -m scripts.create_admin
```

命令要求交互式输入用户名和密码，或者临时读取：

```env
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=强随机密码
```

初始化完成后删除或清空环境变量，并要求首次登录修改密码。

---

## 15. 实施文件清单

### 后端

```text
api/routers/auth.py
api/routers/users.py
api/dependencies.py
api/security.py
api/main.py
api/models.py
db/models.py
```

### 前端

```text
frontend/src/api/auth.ts
frontend/src/api/users.ts
frontend/src/stores/user.ts
frontend/src/router/index.ts
frontend/src/views/Login/index.vue
frontend/src/views/Admin/Users.vue
frontend/src/views/Forbidden/index.vue
```

### SQL

```text
sql/008_user_auth.sql
```

用户自行执行数据库迁移时，应先备份数据库，并按依赖顺序执行角色、用户和会话表迁移。

---

## 16. 验证与安全测试

### 未登录

```text
GET  /api/questionnaire/submit/{id} → 401
POST /api/questionnaire/analyze → 401
POST /api/questionnaire/submit → 401
GET  /api/ai/config → 401
GET  /api/users → 401
```

### 普通用户

```text
POST /api/users → 403
DELETE /api/users/{id} → 403
读取其他用户任务 → 404 或 403
取消其他用户任务 → 404 或 403
```

### 管理员

```text
创建用户 → 200
编辑用户 → 200
禁用用户 → 200
撤销会话 → 旧 Token 立即失效
```

### Token

```text
过期 Access Token → 401
篡改 Token → 401
禁用用户旧 Token → 401
注销后的 Refresh Token → 401
重复使用已轮换 Refresh Token → 401
```

### 自动化测试

建议新增：

```text
test/test_auth.py
test/test_user_management.py
test/test_authorization.py
test/test_task_ownership.py
test/test_security_headers.py
```

---

## 17. 上线检查清单

- [ ] 已删除 `local-demo-token` 回退；
- [ ] `/api/auth/login` 已实现并使用 Argon2id；
- [ ] 所有业务路由都有 `get_current_user`；
- [ ] 用户管理路由都有管理员权限依赖；
- [ ] 任务和 AI 配置有用户归属校验；
- [ ] Refresh Token 只保存哈希；
- [ ] 已实现注销、轮换和禁用用户会话撤销；
- [ ] CORS 不再使用通配符；
- [ ] 已配置 CSRF 防护；
- [ ] 已配置登录限速和锁定；
- [ ] 已配置 SSRF 防护；
- [ ] 日志和错误响应已脱敏；
- [ ] 生产环境已关闭或保护 `/docs`、`/redoc`；
- [ ] 已完成未登录、越权和 Token 失效测试；
- [ ] 已完成数据库备份和迁移回滚方案。

---

## 18. 最终安全边界

系统必须满足以下行为：

```text
未登录访问前端业务页面
→ 跳转登录页

未登录直接调用后端业务接口
→ 401

已登录但无权限调用管理接口
→ 403

已登录但访问其他用户资源
→ 404 或 403

用户被禁用
→ 新请求和旧会话均失效

任务或用户管理操作
→ 写入审计日志
```

只有同时实现“前端路由控制 + 后端统一认证 + 角色权限 + 数据归属校验 + 会话撤销”，才能保证系统不是只做了页面登录，而是真正阻止未授权接口调用和越权访问。
