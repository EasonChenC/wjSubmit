-- 002_ai_configs.sql
-- AI 配置表
-- 用途：替代 ai/config.py 中 AIConfigManager 的内存单例存储。
-- 对应字段：AIConfig.api_key / model / base_url / enabled

CREATE TABLE IF NOT EXISTS ai_configs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
                    -- NULL 表示全局配置（当前单用户模式下的默认行为）；
                    -- 引入登录后，每个用户可拥有自己的一份配置
    api_key         TEXT NOT NULL DEFAULT '',       -- 建议应用层加密后存储，不做明文展示
    model           VARCHAR(128) NOT NULL DEFAULT 'gpt-4o-mini',
    base_url        VARCHAR(255) NOT NULL DEFAULT 'https://api.openai.com/v1',
    enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 全局配置（user_id IS NULL）只允许存在一条
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_configs_global
    ON ai_configs ((user_id IS NULL))
    WHERE user_id IS NULL;

-- 每个用户最多一条配置
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_configs_user
    ON ai_configs (user_id)
    WHERE user_id IS NOT NULL;

CREATE TRIGGER trg_ai_configs_updated_at
    BEFORE UPDATE ON ai_configs
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE ai_configs IS 'AI服务配置（OpenAI兼容接口），替代原内存单例AIConfigManager';
COMMENT ON COLUMN ai_configs.api_key IS '建议在应用层加密存储，接口返回时不回显原文（参考 AIConfigResponse.has_api_key）';
