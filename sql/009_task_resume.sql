-- Task stop/resume support. Back up the database before applying.
ALTER TABLE questionnaire_tasks
    ADD COLUMN IF NOT EXISTS submit_max_attempts SMALLINT NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS execution_no INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS execution_token UUID,
    ADD COLUMN IF NOT EXISTS resume_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS consecutive_failure_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_consecutive_failures INTEGER NOT NULL DEFAULT 10,
    ADD COLUMN IF NOT EXISTS last_resumed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ;

-- Some older databases still carry the original 1..5 proportional retry
-- constraint even though the application and 007 migration support 1..10.
ALTER TABLE questionnaire_tasks
    ALTER COLUMN proportion_max_submit_attempts SET DEFAULT 10;
ALTER TABLE questionnaire_tasks
    DROP CONSTRAINT IF EXISTS ck_questionnaire_tasks_proportion_attempts;
ALTER TABLE questionnaire_tasks
    DROP CONSTRAINT IF EXISTS questionnaire_tasks_proportion_max_submit_attempts_check;
ALTER TABLE questionnaire_tasks
    ADD CONSTRAINT ck_questionnaire_tasks_proportion_attempts
    CHECK (proportion_max_submit_attempts BETWEEN 1 AND 10);

ALTER TABLE task_submissions
    ADD COLUMN IF NOT EXISTS attempt_no INTEGER NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS execution_no INTEGER NOT NULL DEFAULT 1;

ALTER TABLE task_submissions DROP CONSTRAINT IF EXISTS uq_task_submissions_task_index;
ALTER TABLE task_submissions DROP CONSTRAINT IF EXISTS uq_task_submissions_task_index_attempt;
ALTER TABLE task_submissions ADD CONSTRAINT uq_task_submissions_task_index_attempt UNIQUE(task_id, submit_index, attempt_no);
CREATE UNIQUE INDEX IF NOT EXISTS uq_task_submissions_success_index ON task_submissions(task_id, submit_index) WHERE status='success';
CREATE INDEX IF NOT EXISTS idx_task_submissions_resume_lookup ON task_submissions(task_id, submit_index, status, attempt_no DESC);
CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_execution ON questionnaire_tasks(status, heartbeat_at);
