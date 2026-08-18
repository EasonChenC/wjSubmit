-- 006_ai_text_answer_pools.sql
-- 在已有数据库上接入“AI单行/多行文本批量预生成 + 持久化答案池”。

ALTER TABLE questionnaire_tasks
    ADD COLUMN IF NOT EXISTS ai_text_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS ai_text_batch_size SMALLINT NOT NULL DEFAULT 20,
    ADD COLUMN IF NOT EXISTS ai_text_max_attempts SMALLINT NOT NULL DEFAULT 3,
    ADD COLUMN IF NOT EXISTS ai_text_status VARCHAR(16) NOT NULL DEFAULT 'disabled',
    ADD COLUMN IF NOT EXISTS ai_text_generated_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS ai_text_model VARCHAR(128),
    ADD COLUMN IF NOT EXISTS ai_text_error TEXT;

DO $$ BEGIN
    ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_ai_text_batch_size
        CHECK (ai_text_batch_size BETWEEN 1 AND 50);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_ai_text_attempts
        CHECK (ai_text_max_attempts BETWEEN 1 AND 5);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_ai_text_status
        CHECK (ai_text_status IN ('disabled', 'pending', 'generating', 'ready', 'failed', 'cancelled'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS task_text_answer_pools (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES questionnaire_tasks(id) ON DELETE CASCADE,
    question_id     VARCHAR(128) NOT NULL,
    question_label  TEXT NOT NULL,
    answers         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_text_pool_question UNIQUE (task_id, question_id),
    CONSTRAINT ck_task_text_pool_answers_array CHECK (jsonb_typeof(answers) = 'array')
);

CREATE INDEX IF NOT EXISTS idx_task_text_answer_pools_task_id
    ON task_text_answer_pools (task_id);

DROP TRIGGER IF EXISTS trg_task_text_answer_pools_updated_at ON task_text_answer_pools;
CREATE TRIGGER trg_task_text_answer_pools_updated_at
    BEFORE UPDATE ON task_text_answer_pools
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE task_text_answer_pools IS
    'AI文本题答案池：answers数组下标0对应submit_index=1';
