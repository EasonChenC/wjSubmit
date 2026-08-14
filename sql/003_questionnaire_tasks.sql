-- 003_questionnaire_tasks.sql
-- 问卷任务表
-- 用途：核心表。/api/questionnaire/analyze 分析出的完整 QuestionnaireSchema
-- （题目、选项、量表识别、正反向题、positive_values/negative_values等）
-- 落地到 analyzed_schema 字段；/api/questionnaire/submit 提交时直接读取
-- 该字段作为生成答案的唯一依据，不再重新访问问卷页面重新分析。

CREATE TABLE IF NOT EXISTS questionnaire_tasks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE SET NULL,
                        -- 当前单用户模式下可为空

    -- 问卷来源信息
    url                 VARCHAR(500) NOT NULL,
    title               VARCHAR(500),                -- 问卷标题，如 "员工副业意向调查问卷"
    activity_id         VARCHAR(128),               -- 从URL解析出的问卷活动ID，如 "eLeS3jD"
    platform            VARCHAR(32),                 -- wjx / wjcn / tencent / unknown

    -- 分析阶段结果（对应 analyze_questionnaire 的产出）
    -- 结构参考 core.schema.QuestionnaireSchema.to_dict()，
    -- 包含 questions[].metadata 中的 is_scale/is_reverse/positive_values/
    -- negative_values/detection_method 等，是 submit 阶段生成答案的唯一依据
    analyzed_schema     JSONB NOT NULL,
    detection_method    VARCHAR(16) NOT NULL DEFAULT 'keyword'
                        CHECK (detection_method IN ('keyword', 'ai')),
    total_questions     INTEGER NOT NULL DEFAULT 0,
    scale_questions     INTEGER NOT NULL DEFAULT 0,
    reverse_items       JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 反向题ID列表

    -- 提交阶段配置（对应 SubmitRequest / SubmitConfig）
    submit_mode         VARCHAR(32) NOT NULL DEFAULT 'random'
                        CHECK (submit_mode IN ('random', 'high_reliability')),
    attitude            VARCHAR(16) NOT NULL DEFAULT 'positive'
                        CHECK (attitude IN ('positive', 'negative')),
    add_variation       BOOLEAN NOT NULL DEFAULT FALSE,
    variation_ratio     NUMERIC(4, 3) NOT NULL DEFAULT 0.05,  -- 0.01 ~ 0.30

    -- 执行进度（对应 TaskStatusResponse）
    status              VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    total_count         INTEGER NOT NULL DEFAULT 1,   -- 计划提交份数
    submitted_count     INTEGER NOT NULL DEFAULT 0,   -- 成功份数
    failed_count        INTEGER NOT NULL DEFAULT 0,   -- 失败份数
    progress            SMALLINT NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    error_message       TEXT,                          -- 任务级致命错误（如页面无法访问）
    cancel_requested    BOOLEAN NOT NULL DEFAULT FALSE, -- 停止任务请求标记，后台循环轮询该字段优雅停止

    started_at          TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_user_id
    ON questionnaire_tasks (user_id);

CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_status
    ON questionnaire_tasks (status);

CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_created_at
    ON questionnaire_tasks (created_at DESC);

-- 按活动ID查询同一问卷的历史任务
CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_activity_id
    ON questionnaire_tasks (activity_id);

-- 支持对 analyzed_schema 内部字段做条件查询（如筛选含反向题的任务）
CREATE INDEX IF NOT EXISTS idx_questionnaire_tasks_schema_gin
    ON questionnaire_tasks USING GIN (analyzed_schema);

CREATE TRIGGER trg_questionnaire_tasks_updated_at
    BEFORE UPDATE ON questionnaire_tasks
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE questionnaire_tasks IS '问卷任务表：analyze阶段的完整schema落地存储，submit阶段直接复用，不重新分析';
COMMENT ON COLUMN questionnaire_tasks.title IS '问卷标题，从HTML <h1 class="htitle"> 提取';
COMMENT ON COLUMN questionnaire_tasks.cancel_requested IS '停止任务请求标记：置为TRUE后，后台提交循环在下一次迭代开始前检测到会优雅停止，状态置为cancelled';
COMMENT ON COLUMN questionnaire_tasks.analyzed_schema IS '完整问卷结构（含量表识别/正反向题/positive_values/negative_values），是生成答案的唯一依据';
COMMENT ON COLUMN questionnaire_tasks.detection_method IS '该次分析使用的检测方式：keyword(关键字) 或 ai';
