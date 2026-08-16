-- 005_proxy_integration.sql
-- 为已经存在的数据库增加任务级代理策略和单份代理执行记录。

ALTER TABLE questionnaire_tasks
    ADD COLUMN IF NOT EXISTS browser_debug BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS proxy_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS proxy_provider VARCHAR(32),
    ADD COLUMN IF NOT EXISTS proxy_area VARCHAR(64),
    ADD COLUMN IF NOT EXISTS proxy_carrier SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proxy_rotate_per_submission BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS proxy_dedup BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS proxy_verify_exit BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS proxy_location_match VARCHAR(16) NOT NULL DEFAULT 'relaxed',
    ADD COLUMN IF NOT EXISTS proxy_required BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS proxy_max_acquire_attempts SMALLINT NOT NULL DEFAULT 3;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_questionnaire_tasks_proxy_provider') THEN
        ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proxy_provider
            CHECK (proxy_provider IS NULL OR proxy_provider IN ('kuaidaili'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_questionnaire_tasks_proxy_carrier') THEN
        ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proxy_carrier
            CHECK (proxy_carrier BETWEEN 0 AND 3);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_questionnaire_tasks_proxy_location_match') THEN
        ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proxy_location_match
            CHECK (proxy_location_match IN ('strict', 'relaxed'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_questionnaire_tasks_proxy_attempts') THEN
        ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proxy_attempts
            CHECK (proxy_max_acquire_attempts BETWEEN 1 AND 5);
    END IF;
END $$;

ALTER TABLE task_submissions
    ADD COLUMN IF NOT EXISTS proxy_host VARCHAR(255),
    ADD COLUMN IF NOT EXISTS proxy_port INTEGER,
    ADD COLUMN IF NOT EXISTS proxy_requested_area VARCHAR(64),
    ADD COLUMN IF NOT EXISTS proxy_reported_location VARCHAR(128),
    ADD COLUMN IF NOT EXISTS proxy_city_code VARCHAR(32),
    ADD COLUMN IF NOT EXISTS proxy_carrier VARCHAR(32),
    ADD COLUMN IF NOT EXISTS proxy_exit_ip VARCHAR(64),
    ADD COLUMN IF NOT EXISTS proxy_remaining_seconds INTEGER,
    ADD COLUMN IF NOT EXISTS proxy_latency_ms INTEGER,
    ADD COLUMN IF NOT EXISTS proxy_attempts SMALLINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS failure_stage VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_proxy_area
    ON questionnaire_tasks (proxy_area) WHERE proxy_enabled = TRUE;

CREATE INDEX IF NOT EXISTS idx_task_submissions_proxy_exit_ip
    ON task_submissions (proxy_exit_ip) WHERE proxy_exit_ip IS NOT NULL;

COMMENT ON COLUMN questionnaire_tasks.proxy_area IS '任务要求的代理地区；代理API凭据不进入数据库';
COMMENT ON COLUMN questionnaire_tasks.proxy_required IS 'TRUE时代理异常禁止回退本机直连';
COMMENT ON COLUMN task_submissions.proxy_host IS '代理主机/IP，不含认证信息';
COMMENT ON COLUMN task_submissions.failure_stage IS '失败阶段，如proxy_acquire_context、business_submission';
