-- 004_task_submissions.sql
-- 任务提交明细表
-- 用途：一个 questionnaire_tasks 会批量提交N份问卷（count份），
-- 本表记录每一份的具体执行情况，对应当前内存结构中的
-- tasks[task_id]["results"] 数组（index/status/error）。
-- 用于前端展示"每个提交任务具体的执行情况"。

CREATE TABLE IF NOT EXISTS task_submissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES questionnaire_tasks(id) ON DELETE CASCADE,

    submit_index    INTEGER NOT NULL,               -- 第几份提交，1-based，对应 SubmitResult.index
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'success', 'failed')),
    error_message   TEXT,                            -- 失败原因

    -- 本份提交实际生成并填写的答案（对应 DynamicAnswerGenerator.generate_answers() 的输出）
    -- 保留下来便于复盘"这次提交具体填了什么"，排查异常提交或统计答案分布
    generated_answers  JSONB,

    -- 单份提交使用的脱敏代理执行记录，不保存代理用户名、密码或API签名
    proxy_host                 VARCHAR(255),
    proxy_port                 INTEGER,
    proxy_requested_area       VARCHAR(64),
    proxy_reported_location    VARCHAR(128),
    proxy_city_code            VARCHAR(32),
    proxy_carrier              VARCHAR(32),
    proxy_exit_ip              VARCHAR(64),
    proxy_remaining_seconds    INTEGER,
    proxy_latency_ms           INTEGER,
    proxy_attempts             SMALLINT NOT NULL DEFAULT 0,
    failure_stage              VARCHAR(32),

    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_task_submissions_task_index UNIQUE (task_id, submit_index)
);

CREATE INDEX IF NOT EXISTS idx_task_submissions_task_id
    ON task_submissions (task_id);

CREATE INDEX IF NOT EXISTS idx_task_submissions_status
    ON task_submissions (status);

COMMENT ON TABLE task_submissions IS '任务提交明细表：记录批量提交中每一份的执行状态与生成的答案';
COMMENT ON COLUMN task_submissions.generated_answers IS '该份提交实际生成的答案字典，便于复盘和统计';
COMMENT ON COLUMN task_submissions.proxy_host IS '代理主机/IP，不含认证信息';
COMMENT ON COLUMN task_submissions.failure_stage IS '失败阶段，如proxy_acquire_context、business_submission';
