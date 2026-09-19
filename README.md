# 问卷自动化管理系统

一个基于 FastAPI、Vue 3 和 PostgreSQL 的问卷分析与任务管理系统。系统通过 Playwright 获取并解析问卷页面，将解析结果持久化为任务，支持配置答案生成策略、批量执行、进度查询、暂停后恢复，以及可选的 AI 文本答案和动态代理能力。

> **使用边界**
>
> 本项目仅用于获得授权的安全研究、自动化测试和防御能力验证。使用前请确认已经取得问卷平台及相关数据所有者的明确授权。
>
> 禁止将本项目用于制造虚假问卷数据、商业欺诈、学术造假、绕过平台限制或其他违法违规活动。请控制请求频率，避免对第三方服务造成影响。

## 当前能力

- 问卷页面结构分析：题目、题型、选项、必填状态和题目顺序
- 反向题识别：关键词规则识别，或使用已配置的 AI 进行识别
- 三种任务模式：`random`、`high_reliability`、`proportional`
- 比例模式：为支持的单选、多选和矩阵题生成可复现的比例答案计划
- 文本题答案池：可选用 AI 批量预生成单行和多行文本答案，并持久化生成进度
- 任务管理：列表、详情、分析结果、配置修改、取消、恢复和删除
- 任务执行记录：成功/失败明细、重试次数、失败阶段、进度和心跳状态
- 用户与权限：登录、刷新令牌、退出登录、密码修改、管理员用户管理和审计日志
- 动态代理：可选集成快代理，支持地区、运营商、去重、出口验证和按份轮换
- Web 管理界面：Vue 3 + Element Plus，包含任务、分析、AI 设置和用户管理页面
- API 文档与健康检查：FastAPI 自动生成 `/docs`、`/redoc`，并提供 `/health`

## 技术栈

### 后端

- Python 3.10+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 Async ORM + asyncpg
- PostgreSQL
- Playwright Chromium
- Pydantic 2
- JWT、Argon2、HttpOnly Cookie
- OpenAI 兼容接口（可选）

### 前端

- Vue 3
- TypeScript
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios

## 项目结构

```text
.
├── api/                         # FastAPI 应用、数据模型和路由
│   ├── main.py                  # API 应用入口
│   └── routers/                 # auth、users、questionnaire、ai
├── core/                        # 问卷解析、答案生成、提交和比例计划
├── db/                          # SQLAlchemy 模型和异步数据库会话
├── sql/                         # PostgreSQL 初始化/升级脚本
├── proxy/                       # 快代理配置、获取、校验和限流
├── ai/                          # AI 客户端、配置和文本答案池
├── evasion/                     # 浏览器与行为模拟相关模块
├── scheduler/                   # 任务调度相关模块
├── frontend/                    # Vue 3 前端
├── scripts/                     # 管理脚本，例如创建管理员
├── test/                        # pytest 测试和测试数据
├── file/                        # 项目设计、实现和测试文档
├── run_api.py                   # Windows 兼容的 API 启动脚本
├── start_api.bat                # Windows 启动快捷脚本
├── requirements.txt             # Python 依赖
└── .env.example                 # 环境变量模板
```

## 环境要求

- Python 3.10 或更高版本
- Node.js 18+ 和 npm
- PostgreSQL 14+（建议使用支持 `gen_random_uuid()` 的版本）
- 可用的 Chromium 浏览器，或通过 Playwright 安装

## 快速开始

### 1. 安装后端依赖

在项目根目录执行：

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 2. 创建 PostgreSQL 数据库并初始化表

复制环境变量模板：

```bash
copy .env.example .env
```

然后编辑 `.env`，至少设置：

```dotenv
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:<port>/<database>
JWT_SECRET=请替换为随机的高强度密钥
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

按文件名顺序执行 `sql/` 目录中的脚本。建议先执行 `000_extensions.sql`，再执行其余编号脚本：

```bash
psql "$DATABASE_URL" -f sql/000_extensions.sql
psql "$DATABASE_URL" -f sql/001_roles.sql
psql "$DATABASE_URL" -f sql/001_users.sql
psql "$DATABASE_URL" -f sql/002_ai_configs.sql
psql "$DATABASE_URL" -f sql/003_questionnaire_tasks.sql
psql "$DATABASE_URL" -f sql/004_task_submissions.sql
psql "$DATABASE_URL" -f sql/005_proxy_integration.sql
psql "$DATABASE_URL" -f sql/006_ai_text_answer_pools.sql
psql "$DATABASE_URL" -f sql/007_proportional_submission.sql
psql "$DATABASE_URL" -f sql/008_user_auth.sql
psql "$DATABASE_URL" -f sql/009_task_resume.sql
```

如果数据库工具不支持 `$DATABASE_URL` 这种写法，请使用对应的主机、端口、数据库名、用户名和密码参数执行。

### 3. 创建初始管理员

交互式创建：

```bash
python scripts/create_admin.py
```

也可以通过环境变量提供账号，适合自动化部署：

```bash
# PowerShell
$env:INITIAL_ADMIN_USERNAME = "admin"
$env:INITIAL_ADMIN_PASSWORD = "请使用符合密码策略的强密码"
python scripts/create_admin.py
```

### 4. 启动后端

Windows 推荐：

```bash
python run_api.py
```

或者：

```bash
.\start_api.bat
```

后端默认监听 `http://localhost:8000`：

- API 根信息：`http://localhost:8000/`
- 健康检查：`http://localhost:8000/health`
- Swagger 文档：`http://localhost:8000/docs`
- ReDoc 文档：`http://localhost:8000/redoc`

`run_api.py` 会在 Windows 上设置 `WindowsSelectorEventLoopPolicy`，并默认关闭 Uvicorn reload，以避免 Playwright 与子进程重载冲突。

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端默认地址为 `http://localhost:5173`。如需覆盖后端地址，可在 `frontend` 目录创建 `.env.local`：

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

生产构建：

```bash
npm run build
npm run preview
```

## 使用流程

1. 使用管理员账号登录 Web 管理界面。
2. 在任务页面输入已获授权的问卷 URL，执行问卷分析。
3. 检查题目、题型、量表题和反向题识别结果。
4. 选择提交模式并设置任务数量、态度、变化策略、代理策略或 AI 文本答案池。
5. 创建任务后查看实时进度和每份提交结果。
6. 对已取消或失败且仍有剩余数量的任务执行恢复。
7. 管理员可以在用户管理页面维护账号和角色，也可以在 AI 设置页面配置 AI 兼容接口。

### 提交模式

| 模式 | 说明 |
| --- | --- |
| `random` | 使用常规随机答案策略 |
| `high_reliability` | 使用更保守的答案与提交配置，并支持变化比例和重试设置 |
| `proportional` | 按题目选项目标比例生成并持久化答案计划 |

## 配置说明

`.env.example` 包含完整配置模板。常用配置如下：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 异步连接串，必填 |
| `JWT_SECRET` | JWT 签名密钥，生产环境必须替换 |
| `ACCESS_TOKEN_MINUTES` | Access Token 有效期 |
| `REFRESH_TOKEN_DAYS` | Refresh Token 有效期 |
| `COOKIE_SECURE` | HTTPS 部署时建议设为 `true` |
| `CORS_ORIGINS` | 前端允许的明确来源列表，不要使用 `*` |
| `KDL_ENABLED` | 是否启用快代理供应商能力 |
| `KDL_*` | 快代理凭据、地区、限流、校验和轮换策略 |

AI 的 API Key、模型和 Base URL 通过管理员页面保存到数据库，不应提交到 Git。代理供应商凭据仅通过环境变量提供，任务配置只保存非敏感策略。

## 测试

后端测试使用 pytest。安装依赖后可运行：

```bash
pytest
```

只运行基础测试：

```bash
pytest test/test_basic.py
```

涉及 PostgreSQL、代理供应商、Playwright 或外部 AI 服务的测试，运行前请准备相应环境；没有外部依赖时可先运行纯逻辑测试，例如答案策略、比例计划和模型校验测试。

## 安全注意事项

- 只对自己拥有或明确获准测试的问卷执行分析和自动化操作。
- 不要把 `.env`、API Key、代理凭据、生产数据库连接串提交到仓库。
- 生产环境使用 HTTPS，并设置 `COOKIE_SECURE=true`。
- `CORS_ORIGINS` 只填写实际前端来源。
- 对任务数量、并发度和访问频率设置合理上限。
- 定期检查审计日志、失败任务和异常出口 IP。
- 变更数据库模型时，应同步更新 `db/models.py` 和 `sql/` 脚本。

## 相关文档

- [快速开始](file/快速开始.md)
- [技术实现文档](file/技术实现文档.md)
- [项目总结](file/项目总结.md)
- [开放型文本输入题的回答策略](file/开放型文本输入题的回答策略.md)
- [快代理集成设计](proxy/KUAIDAILI_PROXY_INTEGRATION_DESIGN.md)

## 许可证

当前仓库未声明具体开源许可证。除非获得项目维护者和相关权利人的明确许可，请不要将其作为开源软件再分发或用于生产服务。
