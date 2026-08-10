-- 000_extensions.sql
-- 基础扩展与公共函数
-- 用途：为所有表提供 UUID 生成能力和统一的 updated_at 自动更新触发器

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- 提供 gen_random_uuid()

-- 通用触发器函数：任意表只要有 updated_at 列，绑定此函数即可自动维护更新时间
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
