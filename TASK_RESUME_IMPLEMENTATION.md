# 问卷任务停止与恢复执行模块改造技术实现方案

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档名称 | 问卷任务停止与恢复执行模块改造技术实现方案 |
| 适用系统 | 问卷自动化系统 |
| 适用模式 | `random`、`high_reliability`、`proportional` |
| 目标版本 | 用户认证与任务归属改造后的版本 |
| 核心目标 | 任务停止或可恢复失败后，从持久化断点继续执行，直到成功提交数达到目标数 |

---

## 2. 背景与问题

当前任务创建后由 `submit_questionnaire_task()` 在后台执行。用户可以调用停止接口设置 `cancel_requested=true`，执行器在下一轮开始前检测该标志并优雅停止。

现有模型将 `total_count` 理解为循环次数，而业务需求实际要求它表示“目标成功提交数”。当前实现存在以下问题：

1. 后台执行器每次启动都把 `success_count`、`fail_count` 重置为零；
2. 循环始终从 `submit_index=1` 开始，停止后不能从数据库断点继续；
3. `task_submissions` 当前对 `(task_id, submit_index)` 设置唯一约束，无法记录同一目标序号的多次失败尝试；
4. 进度按已执行次数计算，而不是按成功提交数计算；
5. 单个成功配额重试耗尽后会终止整个任务；
6. 循环退出即可能被设置为 `completed`，没有再次验证成功数是否达到目标；
7. 比例模式、AI 文本答案池虽然已经持久化，但执行器没有按照未成功序号恢复；
8. 缺少恢复 API、并发恢复保护、执行批次标识和恢复审计；
9. 服务异常终止后，遗留的 `processing` 状态没有明确恢复策略。

---

## 3. 改造目标

### 3.1 功能目标

任务需满足：

```text
total_count     = 目标成功提交数
submitted_count = 本地已确认成功数
failed_count    = 历史失败尝试数
remaining_count = max(total_count - submitted_count, 0)
progress        = floor(submitted_count / total_count * 100)
```

只有满足以下条件时，任务才可进入 `completed`：

```python
submitted_count >= total_count
```

停止后的任务应支持恢复：

```text
cancelled -> pending -> processing -> completed
failed    -> pending -> processing -> completed
```

恢复后不得重新分析问卷、不得重置任务配置、不得重复消费已成功的目标序号。

### 3.2 权限目标

```text
普通用户：只能停止、恢复、查看自己创建的任务
管理员：可以停止、恢复、查看所有任务
任务删除：仍然仅管理员允许
```

对无权访问的任务统一返回 `404`，避免暴露任务是否存在。

### 3.3 一致性目标

1. 同一任务在任意时刻最多只能有一个有效执行器；
2. 重复点击恢复不得启动多个后台执行器；
3. 每个目标成功序号最多只能存在一条 `success` 记录；
4. 随机、高可靠及比例模式均按持久化序号恢复；
5. AI 文本答案与比例计划必须复用原有持久化数据；
6. 每次停止、恢复、完成和失败均可审计。

---

## 4. 范围说明

### 4.1 本次改造范围

- PostgreSQL 表结构和索引；
- SQLAlchemy ORM；
- 后台任务执行循环；
- 停止与恢复 API；
- 任务状态和进度计算；
- 三种提交模式的断点恢复；
- 前端任务详情页及任务列表操作；
- 审计日志；
- 自动化测试；
- 历史数据迁移与回滚方案。

### 4.2 不在本次范围

- 外部问卷平台的提交幂等接口；
- 多节点分布式任务队列的完整替换；
- 对远端已提交、本地未落库的结果进行自动核验；
- 修改已创建任务的目标数量、问卷结构或比例配置。

---

## 5. 术语与语义

### 5.1 目标成功序号 `submit_index`

`submit_index` 表示第几个成功配额，范围固定为：

```text
1..total_count
```

例如目标为100份，序号38可能经历：

```text
submit_index=38, attempt_no=1, status=failed
submit_index=38, attempt_no=2, status=failed
submit_index=38, attempt_no=3, status=success
```

只有序号38成功后，才认为第38个成功配额完成。

### 5.2 尝试序号 `attempt_no`

同一 `submit_index` 下递增的尝试编号，从1开始。用于区分失败记录以及恢复后的再次尝试。

### 5.3 执行批次 `execution_no`

任务每次首次启动或恢复启动形成一个执行批次：

```text
首次执行 execution_no=1
第一次恢复 execution_no=2
第二次恢复 execution_no=3
```

用于追踪某条提交记录属于哪次启动。

### 5.4 已确认成功

只有外部提交返回成功并且本地 `task_submissions` 成功记录事务提交完成，才计入 `submitted_count`。

---

## 6. 状态机设计

### 6.1 任务状态

继续使用：

```text
pending
processing
completed
failed
cancelled
```

语义如下：

| 状态 | 含义 | 是否可停止 | 是否可恢复 |
|---|---|---:|---:|
| `pending` | 已投递、尚未正式执行 | 是 | 否 |
| `processing` | 执行中 | 是 | 否 |
| `cancelled` | 已响应用户停止请求 | 否 | 是，且成功数未达标 |
| `failed` | 达到连续失败阈值或发生可恢复执行异常 | 否 | 是，且成功数未达标 |
| `completed` | 成功数已达到目标 | 否 | 否 |

### 6.2 状态转换

```text
创建任务
  -> pending
  -> processing

processing + cancel_requested=true
  -> 当前单份安全结束并落库
  -> cancelled

cancelled/failed + resume
  -> pending
  -> processing

processing + submitted_count >= total_count
  -> completed

processing + 连续失败达到阈值
  -> failed
```

### 6.3 状态不变量

```text
completed  => submitted_count >= total_count AND progress = 100
cancelled  => cancel_requested = true
processing => cancel_requested = false AND execution_token IS NOT NULL
pending    => cancel_requested = false
```

执行器退出时必须清空或失效本次 `execution_token`。

---

## 7. 数据库设计

## 7.1 questionnaire_tasks 扩展

建议新增：

```sql
ALTER TABLE questionnaire_tasks
    ADD COLUMN IF NOT EXISTS execution_no INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS execution_token UUID,
    ADD COLUMN IF NOT EXISTS resume_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consecutive_failure_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_consecutive_failures INTEGER NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS last_resumed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

ALTER TABLE questionnaire_tasks
    ADD CONSTRAINT ck_questionnaire_tasks_max_consecutive_failures
    CHECK (max_consecutive_failures BETWEEN 1 AND 100);
```

字段说明：

| 字段 | 用途 |
|---|---|
| `execution_no` | 当前/最近执行批次编号 |
| `execution_token` | 当前执行器租约标识，防止旧执行器继续写入 |
| `resume_count` | 用户恢复次数 |
| `consecutive_failure_count` | 当前连续失败次数，成功后归零 |
| `max_consecutive_failures` | 连续失败熔断阈值 |
| `last_resumed_at` | 最近恢复时间 |
| `heartbeat_at` | 执行器最近心跳时间，用于识别僵尸任务 |

建议索引：

```sql
CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_execution
    ON questionnaire_tasks(status, heartbeat_at);
```

## 7.2 task_submissions 改造

新增字段：

```sql
ALTER TABLE task_submissions
    ADD COLUMN IF NOT EXISTS attempt_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS execution_no INTEGER NOT NULL DEFAULT 1;
```

删除旧唯一约束：

```sql
ALTER TABLE task_submissions
    DROP CONSTRAINT IF EXISTS uq_task_submissions_task_index;
```

增加新的唯一约束与部分唯一索引：

```sql
ALTER TABLE task_submissions
    ADD CONSTRAINT uq_task_submissions_task_index_attempt
    UNIQUE (task_id, submit_index, attempt_no);

CREATE UNIQUE INDEX IF NOT EXISTS uq_task_submissions_success_index
    ON task_submissions(task_id, submit_index)
    WHERE status = 'success';

CREATE INDEX IF NOT EXISTS idx_task_submissions_resume_lookup
    ON task_submissions(task_id, submit_index, status, attempt_no DESC);
```

数据库保证：

1. 同一目标序号的尝试号不可重复；
2. 同一目标序号最多一条成功记录；
3. 失败记录可保留多条；
4. 恢复时可快速获取成功序号和下一尝试号。

## 7.3 迁移文件

新增：

```text
sql/009_task_resume.sql
```

迁移顺序：

```text
008_user_auth.sql
009_task_resume.sql
```

### 7.3.1 历史提交数据迁移

现有每个 `(task_id, submit_index)` 最多一条记录，可安全初始化：

```sql
UPDATE task_submissions
SET attempt_no = 1,
    execution_no = 1
WHERE attempt_no IS NULL OR execution_no IS NULL;
```

迁移前必须检查是否存在重复成功序号：

```sql
SELECT task_id, submit_index, count(*)
FROM task_submissions
WHERE status = 'success'
GROUP BY task_id, submit_index
HAVING count(*) > 1;
```

结果必须为空。

---

## 8. ORM 改造

在 `db/models.py` 中同步增加字段：

```python
class QuestionnaireTask(Base):
    execution_no: Mapped[int]
    execution_token: Mapped[Optional[uuid.UUID]]
    resume_count: Mapped[int]
    consecutive_failure_count: Mapped[int]
    max_consecutive_failures: Mapped[int]
    last_resumed_at: Mapped[Optional[datetime]]
    heartbeat_at: Mapped[Optional[datetime]]

class TaskSubmission(Base):
    attempt_no: Mapped[int]
    execution_no: Mapped[int]
```

并将 ORM 的旧唯一约束：

```python
UniqueConstraint("task_id", "submit_index", ...)
```

替换为：

```python
UniqueConstraint(
    "task_id", "submit_index", "attempt_no",
    name="uq_task_submissions_task_index_attempt",
)
```

部分唯一索引应使用 SQLAlchemy `Index(..., postgresql_where=...)` 或仅由迁移维护。

---

## 9. 后端核心执行器改造

## 9.1 原则

执行器启动时不得使用内存初始值推断断点，必须从数据库重建：

```python
success_indexes = 查询 status='success' 的 submit_index
submitted_count = len(success_indexes)
failed_count = 查询 status='failed' 的总数
remaining_indexes = [1..total_count] - success_indexes
```

`questionnaire_tasks` 中的计数字段是缓存/展示字段，启动时应根据明细校准。

## 9.2 执行租约

恢复接口或首次提交接口生成：

```python
execution_token = uuid.uuid4()
execution_no += 1
```

后台执行函数签名改为：

```python
async def submit_questionnaire_task(
    task_id: str,
    execution_token: str,
) -> None:
```

每次提交前检查：

```python
await session.refresh(task_row)
if str(task_row.execution_token) != execution_token:
    return
```

旧执行器失去租约后立即退出，不再修改任务状态。

## 9.3 断点重建函数

建议新增：

```python
@dataclass
class TaskCheckpoint:
    success_indexes: set[int]
    submitted_count: int
    failed_count: int
    remaining_indexes: list[int]

async def load_task_checkpoint(
    session: AsyncSession,
    task: QuestionnaireTask,
) -> TaskCheckpoint:
    ...
```

校验：

```text
成功序号必须在 1..total_count
成功序号不得重复（数据库索引同时保证）
submitted_count 不得大于 total_count
```

随后校准任务字段：

```python
task.submitted_count = checkpoint.submitted_count
task.failed_count = checkpoint.failed_count
task.progress = int(checkpoint.submitted_count * 100 / task.total_count)
```

## 9.4 下一尝试号

```python
async def next_attempt_no(session, task_id, submit_index) -> int:
    latest = await session.scalar(
        select(func.max(TaskSubmission.attempt_no)).where(
            TaskSubmission.task_id == task_id,
            TaskSubmission.submit_index == submit_index,
        )
    )
    return (latest or 0) + 1
```

如果未来使用多进程队列，应通过行锁或数据库序列化保护。当前执行租约保证单任务只有一个执行器。

## 9.5 新执行循环

推荐伪代码：

```python
async def submit_questionnaire_task(task_id, execution_token):
    task = load_task_with_lock_or_validate_token()
    checkpoint = await load_task_checkpoint(session, task)

    if checkpoint.submitted_count >= task.total_count:
        mark_completed()
        return

    task.status = "processing"
    task.started_at = task.started_at or now()
    task.finished_at = None
    task.heartbeat_at = now()
    commit()

    schema = restore_schema()
    generator = restore_generator_config()
    text_pools = await prepare_text_answer_pools(...)
    proportion_plans = await prepare_proportion_answer_plans(...)

    for submit_index in checkpoint.remaining_indexes:
        while True:
            refresh_task()
            validate_execution_token()

            if task.cancel_requested:
                mark_cancelled()
                return

            attempt_no = await next_attempt_no(...)
            submission = TaskSubmission(
                task_id=task.id,
                submit_index=submit_index,
                attempt_no=attempt_no,
                execution_no=task.execution_no,
                status="pending",
            )

            answers = build_or_restore_answers(submit_index)
            result = await execute_with_inner_attempts(...)

            if result.success:
                submission.status = "success"
                task.submitted_count += 1
                task.consecutive_failure_count = 0
                task.progress = floor(
                    task.submitted_count / task.total_count * 100
                )
                commit()
                break

            submission.status = "failed"
            task.failed_count += 1
            task.consecutive_failure_count += 1
            commit()

            if task.consecutive_failure_count >= task.max_consecutive_failures:
                mark_failed()
                return

            await backoff(task.consecutive_failure_count)

    reload_checkpoint()
    if checkpoint.submitted_count >= task.total_count:
        mark_completed()
    else:
        mark_failed("Execution ended before target was reached")
```

## 9.6 内部重试与外部尝试

需要区分两层：

```text
内部重试：一次 task_submissions 尝试内，重新获取代理/上下文，最多 submit_max_attempts 次
外部尝试：内部重试全部失败后，新增一条 failed 明细，再对同一 submit_index 建立下一 attempt_no
```

内部重试沿用当前配置。外部尝试受连续失败熔断和退避控制。

建议退避：

```python
BACKOFF_SECONDS = [5, 10, 20, 30, 60]
delay = BACKOFF_SECONDS[min(failure_count - 1, 4)]
```

停止标志在退避期间也应可响应，使用短间隔轮询而不是单次长睡眠。

## 9.7 计数与进度

任何路径都不得再使用：

```python
progress = int((i + 1) / count * 100)
```

统一使用：

```python
progress = min(100, int(submitted_count * 100 / total_count))
```

`failed_count` 表示失败尝试总数，可能大于 `total_count`。

---

## 10. 三种模式恢复策略

## 10.1 随机模式 `random`

### 首次尝试

按照现有 `DynamicAnswerGenerator` 生成答案，并持久化到：

```text
task_submissions.generated_answers
```

### 同一成功序号重试

优先读取该 `submit_index` 最近一次非空的 `generated_answers`：

```python
answers = await load_previous_answers(task_id, submit_index)
if answers is None:
    answers = generator.generate_answers()
```

这样停止和恢复不会导致同一成功配额的答案不断变化。

### 成功后

进入下一个未成功 `submit_index`，生成新的答案。

## 10.2 高可靠模式 `high_reliability`

恢复时复用任务表中的：

```text
attitude
add_variation
variation_ratio
submit_max_attempts
```

普通选择题答案与随机模式相同：同一序号优先复用最近持久化答案。

如果启用 AI 文本答案：

1. `task_text_answer_pools` 按题目保存 `total_count` 份答案；
2. 使用 `submit_index - 1` 作为固定下标；
3. 停止发生在答案池生成期间时，恢复后从当前已有长度继续补齐；
4. 已生成答案不得删除或重新排序；
5. `ai_text_status=cancelled/failed` 的可恢复任务重新启动时，应允许进入 `generating` 并继续生成，而不是因状态本身拒绝。

同一成功序号组合答案：

```python
base_answers = previous_answers_or_generate()
text_overrides = text_overrides_for_submission(pool, submit_index)
base_answers.update(text_overrides)
```

## 10.3 比例模式 `proportional`

比例模式必须保持整个目标集合的确定性分布。

现有 `task_proportion_answer_plans` 已按：

```text
(task_id, submit_index)
```

保存计划，应作为恢复的唯一比例答案来源。

恢复规则：

1. 不重新运行随机比例分配；
2. 读取完整计划并验证序号为 `1..total_count`；
3. 对第一个未成功序号读取对应计划；
4. 该序号失败时始终重试同一计划；
5. 该序号成功后才处理下一个未成功序号；
6. 停止后恢复仍读取同一个计划；
7. 禁止恢复时修改 `proportion_config`、`proportion_plan_seed` 或 `total_count`。

如果比例模式同时启用 AI 文本题：

```python
answer_overrides = proportion_plans[submit_index]
answer_overrides.update(text_overrides_for_submission(pool, submit_index))
```

继续保留两类覆盖字段冲突校验。

---

## 11. 停止接口改造

现有接口保持：

```http
POST /api/questionnaire/submit/{task_id}/cancel
```

### 请求处理

1. 按管理员/所有者范围查询任务；
2. 仅允许 `pending` 或 `processing`；
3. 设置 `cancel_requested=true`；
4. 写入 `task.cancel.requested` 审计；
5. 返回“停止请求已接受”，不提前宣称任务已经停止。

建议响应：

```json
{
  "success": true,
  "data": {
    "task_id": "UUID",
    "status": "processing",
    "cancel_requested": true
  }
}
```

执行器应在以下安全点检查停止：

- AI 文本答案每批生成前；
- 每个目标序号开始前；
- 外部尝试退避期间；
- 每次内部提交尝试结束后。

当前正在外部平台提交的一份不得强制杀死，应等待其结果落库后停止。

---

## 12. 恢复接口设计

新增：

```http
POST /api/questionnaire/submit/{task_id}/resume
```

### 12.1 前置校验

```text
任务存在且当前用户有权访问
status in ('cancelled', 'failed')
submitted_count < total_count
不存在有效执行租约
问卷分析结构存在
比例模式的计划完整
AI 文本模式配置仍可用
代理配置在启用时仍有效
```

AI 或代理配置临时不可用时返回明确的 `409` 或 `422`，不修改任务状态。

### 12.2 原子状态切换

使用单条带条件更新：

```sql
UPDATE questionnaire_tasks
SET status = 'pending',
    cancel_requested = FALSE,
    error_message = NULL,
    finished_at = NULL,
    execution_no = execution_no + 1,
    execution_token = gen_random_uuid(),
    resume_count = resume_count + 1,
    last_resumed_at = now(),
    heartbeat_at = now()
WHERE id = :task_id
  AND status IN ('cancelled', 'failed')
  AND submitted_count < total_count
RETURNING id, execution_no, execution_token;
```

未返回记录时重新查询原因：

```text
404：任务不存在或无权限
409：状态已被其他请求改变、已经运行或已经完成
```

### 12.3 投递执行器

```python
background_tasks.add_task(
    submit_questionnaire_task,
    str(task.id),
    str(task.execution_token),
)
```

### 12.4 响应

```json
{
  "success": true,
  "message": "Task resume requested",
  "data": {
    "task_id": "UUID",
    "status": "pending",
    "submitted": 37,
    "total": 100,
    "remaining": 63,
    "execution_no": 2
  }
}
```

### 12.5 审计

写入：

```text
action: task.resume
resource_type: questionnaire_task
metadata:
  previous_status
  submitted_count
  total_count
  remaining_count
  execution_no
```

---

## 13. 首次启动接口调整

`POST /api/questionnaire/submit` 在首次启动时：

```text
execution_no = 1
execution_token = 新UUID
resume_count = 0
consecutive_failure_count = 0
cancel_requested = false
submitted_count = 0
failed_count = 0
progress = 0
```

投递后台函数时携带 `execution_token`。

已经执行过的任务不得再次调用首次启动接口覆盖原配置，应返回 `409`，恢复必须调用专用 `/resume`。

---

## 14. 服务异常重启策略

仅增加恢复按钮仍无法处理服务进程重启后遗留的 `processing` 状态。

建议在应用启动阶段执行僵尸任务修复：

```text
status in ('pending', 'processing')
AND heartbeat_at < now() - interval '2 minutes'
```

转换为：

```text
status = failed
error_message = 'Worker heartbeat expired'
execution_token = NULL
finished_at = now()
```

随后用户可以点击继续任务。

第一阶段不建议服务启动后自动继续所有任务，因为可能同时存在另一个仍运行的实例。自动恢复应建立在数据库租约和部署实例标识完善后再启用。

---

## 15. API 响应模型调整

`TaskStatusResponse` 增加：

```python
remaining: int
cancel_requested: bool
can_resume: bool
execution_no: int
resume_count: int
consecutive_failure_count: int
max_consecutive_failures: int
creator_id: Optional[str]
creator_username: Optional[str]
```

示例：

```json
{
  "task_id": "UUID",
  "title": "客户满意度调查",
  "status": "cancelled",
  "submitted": 37,
  "failed": 5,
  "total": 100,
  "remaining": 63,
  "progress": 37,
  "can_resume": true,
  "execution_no": 1,
  "resume_count": 0
}
```

任务列表响应同步返回 `remaining` 和 `can_resume`。

---

## 16. 前端改造

## 16.1 API

在 `frontend/src/api/task.ts` 新增：

```typescript
export const resumeTask = (id: string) =>
  request.post<ApiResponse<TaskResumeResult>>(
    `/api/questionnaire/submit/${id}/resume`
  )
```

## 16.2 Store

在 `frontend/src/stores/task.ts` 新增：

```typescript
async resume(id: string) {
  await resumeTask(id)
  return this.refresh(id)
}
```

Store 不在本地自行修改成功数或状态，以后端响应为准。

## 16.3 任务详情页

显示：

```text
任务名称
创建人员
目标成功数
已成功
失败尝试
剩余数量
执行进度
执行批次
恢复次数
```

按钮规则：

```typescript
const canCancel = computed(() =>
  ['pending', 'processing'].includes(task.value?.status ?? '')
)

const canResume = computed(() =>
  ['cancelled', 'failed'].includes(task.value?.status ?? '') &&
  (task.value?.submitted ?? 0) < (task.value?.total ?? 0)
)
```

按钮：

```vue
<el-button v-if="canCancel" type="danger" @click="cancel">
  停止任务
</el-button>

<el-button v-if="canResume" type="primary" @click="resume">
  继续任务
</el-button>
```

恢复确认文案：

```text
任务将从已确认成功的断点继续执行。
当前已成功37份，剩余63份。是否继续？
```

恢复成功后重新开启轮询。

## 16.4 任务列表页

对于 `cancelled` 和可恢复 `failed` 任务显示“继续”操作；删除按钮仍只向管理员显示。

管理员可恢复所有用户任务，普通账号只能收到自己的任务数据，因此前端无需额外实现所有权判断，后端仍必须校验。

---

## 17. 审计与日志

新增审计动作：

```text
task.cancel.requested
task.cancelled
task.resume
task.execution.started
task.execution.failed
task.completed
```

禁止在日志和审计 metadata 中记录：

```text
完整问卷答案
AI Key
代理凭据
Cookie
Token
```

日志建议包含：

```text
task_id
execution_no
submit_index
attempt_no
status
failure_stage
remaining_count
```

---

## 18. 并发与事务设计

### 18.1 恢复并发

两个恢复请求同时到达时，依赖条件更新保证只有一个成功：

```text
请求A：cancelled -> pending，成功
请求B：WHERE status=cancelled 不再匹配，返回409
```

### 18.2 成功记录事务

一次提交结果应在同一个事务中写入：

```text
task_submissions.status = success
questionnaire_tasks.submitted_count += 1
questionnaire_tasks.progress = ...
questionnaire_tasks.consecutive_failure_count = 0
questionnaire_tasks.heartbeat_at = now()
```

### 18.3 失败记录事务

```text
task_submissions.status = failed
questionnaire_tasks.failed_count += 1
questionnaire_tasks.consecutive_failure_count += 1
questionnaire_tasks.heartbeat_at = now()
```

### 18.4 数据库冲突处理

成功部分唯一索引冲突表示该目标序号已被其他执行器成功写入。执行器应：

1. 回滚当前事务；
2. 重新加载检查点；
3. 若该序号已成功则跳过；
4. 校验自己的 `execution_token`；
5. 不重复累加 `submitted_count`。

---

## 19. 远端提交不确定性

外部问卷平台没有本系统可控的幂等键。以下窗口无法被完全消除：

```text
远端已经提交成功
-> 本地进程在写入 success 前崩溃
-> 恢复后本地认为该序号未成功
-> 可能再次提交
```

本次实现的保证边界：

1. 正常点击停止时采用优雅停止，可准确续跑；
2. 本地已确认成功的序号绝不重复执行；
3. 本地进程崩溃造成的远端未知结果可能导致少量超额；
4. 如外部平台未来提供结果查询或幂等键，可将 `submission_key` 传给外部平台实现严格幂等。

可选扩展：增加 `unknown` 状态，要求管理员确认后再恢复，但会降低自动化程度。

---

## 20. 自动化测试方案

新增：

```text
test/test_task_resume.py
test/test_task_resume_authorization.py
test/test_task_resume_modes.py
test/test_task_resume_concurrency.py
```

### 20.1 通用恢复测试

```text
目标10，成功4后停止
-> 状态 cancelled
-> submitted=4
-> remaining=6
-> 恢复
-> 从第5个成功配额继续
-> 最终 submitted=10、progress=100、status=completed
```

### 20.2 重复恢复

```text
对 cancelled 任务并发发送两个 resume
-> 一个200
-> 一个409
-> 仅生成一个新 execution_no
```

### 20.3 权限

```text
普通用户恢复自己的任务 -> 200
普通用户恢复他人任务 -> 404
管理员恢复任意任务 -> 200
未登录恢复任务 -> 401
```

### 20.4 随机模式

```text
同一 submit_index 第一次失败
-> 恢复/重试读取原 generated_answers
-> 成功后才进入下一 submit_index
```

### 20.5 高可靠模式

```text
AI 文本池生成到40/100时停止
-> 恢复后从40继续生成到100
-> 已有40条内容不变化
-> 提交按 submit_index 读取对应内容
```

### 20.6 比例模式

```text
完整计划100份
成功37份后停止
-> 恢复后使用38..100计划
-> 不重新创建计划
-> 最终答案分布与原计划汇总完全一致
```

### 20.7 失败熔断

```text
连续失败达到 max_consecutive_failures
-> status=failed
-> submitted_count不增加
-> 允许后续手动resume
```

### 20.8 停止竞争

```text
一份正在提交时点击停止
-> 当前结果正常落库
-> 不再启动下一份
-> 状态最终为cancelled
```

### 20.9 完成保护

```text
submitted_count == total_count
-> resume返回409
-> completed任务不出现继续按钮
```

---

## 21. 实施文件清单

### 后端

```text
api/routers/questionnaire.py
api/models.py
db/models.py
api/main.py（僵尸任务清理，可选）
```

### 前端

```text
frontend/src/api/task.ts
frontend/src/stores/task.ts
frontend/src/types/index.ts
frontend/src/views/Task/Detail.vue
frontend/src/views/Task/List.vue
```

### SQL

```text
sql/009_task_resume.sql
sql/009_task_resume_rollback.sql
```

### 测试

```text
test/test_task_resume.py
test/test_task_resume_authorization.py
test/test_task_resume_modes.py
test/test_task_resume_concurrency.py
```

---

## 22. 推荐实施顺序

### 阶段一：数据基础

1. 备份数据库；
2. 新增 `009_task_resume.sql`；
3. 更新 ORM；
4. 验证历史提交明细迁移；
5. 验证唯一索引和部分唯一索引。

### 阶段二：执行器

1. 实现检查点加载；
2. 实现执行租约；
3. 重构提交循环为成功配额驱动；
4. 改造进度计算；
5. 加入连续失败熔断和可中断退避；
6. 验证三种模式答案复用。

### 阶段三：接口

1. 改造首次启动；
2. 加入 `/resume`；
3. 增强 `/cancel`；
4. 扩展任务响应字段；
5. 加入审计日志。

### 阶段四：前端

1. 增加继续任务 API；
2. 增加 Store action；
3. 修复详情页中文与任务标题展示；
4. 增加剩余数量和恢复按钮；
5. 在列表增加继续操作。

### 阶段五：测试与上线

1. 单元测试；
2. 数据库集成测试；
3. 三种模式端到端测试；
4. 停止/恢复竞争测试；
5. 上线前备份；
6. 执行迁移；
7. 发布后监控失败率、重复恢复和僵尸任务。

---

## 23. 上线检查清单

- [ ] `total_count` 已统一解释为目标成功数量；
- [ ] 进度只按成功数量计算；
- [ ] `task_submissions` 支持同一序号多次尝试；
- [ ] 同一序号最多一条成功记录；
- [ ] 恢复接口使用数据库原子状态切换；
- [ ] 后台执行器校验 `execution_token`；
- [ ] 随机模式复用同序号答案；
- [ ] 高可靠模式复用并续生成 AI 文本池；
- [ ] 比例模式复用原完整计划；
- [ ] 普通用户只能恢复自己的任务；
- [ ] 管理员可以恢复全部任务；
- [ ] 已完成任务禁止恢复；
- [ ] 恢复、停止、失败、完成写入审计日志；
- [ ] 连续失败存在熔断和退避；
- [ ] 服务重启后的僵尸任务可识别；
- [ ] 数据库迁移和回滚脚本已经演练；
- [ ] 自动化测试全部通过。

---

## 24. 回滚方案

回滚前必须停止 API 和所有后台执行器。

### 24.1 应用回滚

恢复到不调用 `/resume` 且不读取新字段的版本。新增字段本身可暂时保留，不影响旧代码。

### 24.2 数据库回滚注意事项

只有满足以下条件时才能恢复旧唯一约束：

```sql
SELECT task_id, submit_index, count(*)
FROM task_submissions
GROUP BY task_id, submit_index
HAVING count(*) > 1;
```

结果为空。

新版本运行后，同一 `submit_index` 可能已有多条尝试，不能直接恢复旧约束。若必须回滚，需要先归档失败尝试，仅保留每个序号的一条最终记录，再执行：

```sql
DROP INDEX IF EXISTS uq_task_submissions_success_index;
ALTER TABLE task_submissions
    DROP CONSTRAINT IF EXISTS uq_task_submissions_task_index_attempt;
ALTER TABLE task_submissions
    ADD CONSTRAINT uq_task_submissions_task_index
    UNIQUE(task_id, submit_index);
```

因此推荐的生产回滚方式是：

```text
回滚应用代码，但暂时保留009新增字段和索引
```

待确认无需恢复历史尝试后，再单独清理数据库结构。

---

## 25. 最终验收标准

系统必须满足以下行为：

```text
创建目标100份的任务
-> 成功37份后点击停止
-> 当前进行中的单份安全结束并落库
-> 状态进入cancelled
-> 页面显示已成功、失败尝试和剩余数量
-> 点击继续任务
-> 不重新分析问卷
-> 不重复执行本地已确认成功的序号
-> 随机/高可靠模式复用对应答案
-> 比例模式复用对应比例计划
-> 最终成功数达到100
-> progress=100
-> status=completed
```

并且：

```text
重复点击继续不会启动两个执行器
普通用户不能恢复他人的任务
完成任务不能再次恢复
每次恢复均有审计记录
```
