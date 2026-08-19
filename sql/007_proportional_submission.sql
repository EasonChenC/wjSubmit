-- 007_proportional_submission.sql
-- 已有数据库接入按题目选项比例生成确定性答案计划。

ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS ck_questionnaire_tasks_detection_method;
ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS questionnaire_tasks_detection_method_check;
ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_detection_method
    CHECK (detection_method IN ('keyword', 'ai', 'structure'));

ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS ck_questionnaire_tasks_submit_mode;
ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS questionnaire_tasks_submit_mode_check;
ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_submit_mode
    CHECK (submit_mode IN ('random', 'high_reliability', 'proportional'));

ALTER TABLE questionnaire_tasks
    ADD COLUMN IF NOT EXISTS submit_max_attempts SMALLINT NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS proportion_config JSONB,
    ADD COLUMN IF NOT EXISTS proportion_plan_status VARCHAR(16) NOT NULL DEFAULT 'disabled',
    ADD COLUMN IF NOT EXISTS proportion_plan_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proportion_plan_seed INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS proportion_max_submit_attempts SMALLINT NOT NULL DEFAULT 10;

-- ADD COLUMN IF NOT EXISTS does not update defaults on an existing database.
ALTER TABLE questionnaire_tasks
    ALTER COLUMN submit_max_attempts SET DEFAULT 10,
    ALTER COLUMN proportion_max_submit_attempts SET DEFAULT 10;

DO $$ BEGIN
    ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_submit_attempts
        CHECK (submit_max_attempts BETWEEN 1 AND 10);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proportion_status
        CHECK (proportion_plan_status IN ('disabled', 'pending', 'ready', 'failed'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Replace the former 1..5 constraint so proportional mode can also use 10 retries.
ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS ck_questionnaire_tasks_proportion_attempts;
ALTER TABLE questionnaire_tasks DROP CONSTRAINT IF EXISTS questionnaire_tasks_proportion_max_submit_attempts_check;
ALTER TABLE questionnaire_tasks ADD CONSTRAINT ck_questionnaire_tasks_proportion_attempts
    CHECK (proportion_max_submit_attempts BETWEEN 1 AND 10);

CREATE TABLE IF NOT EXISTS task_proportion_answer_plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID NOT NULL REFERENCES questionnaire_tasks(id) ON DELETE CASCADE,
    submit_index    INTEGER NOT NULL,
    answers         JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_proportion_plan_index UNIQUE (task_id, submit_index),
    CONSTRAINT ck_task_proportion_plan_answers_object CHECK (jsonb_typeof(answers) = 'object')
);

CREATE INDEX IF NOT EXISTS idx_task_proportion_answer_plans_task_id
    ON task_proportion_answer_plans (task_id);

COMMENT ON TABLE task_proportion_answer_plans IS
    '比例提交模式的确定性答案计划；submit_index对应第N份问卷';
