-- 001_users.sql
-- 用户表
-- 用途：后续引入登录/多用户隔离时使用。当前阶段任务和AI配置的 user_id 均可为空，
-- 表示"未启用多用户"的兼容模式；一旦启用认证，新数据应带上真实 user_id。

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(64) NOT NULL,
    email           VARCHAR(255),
    password_hash   VARCHAR(255) NOT NULL,          -- 存哈希后的密码，禁止存明文
    role_id         SMALLINT NOT NULL DEFAULT 2
                    REFERENCES roles(id) ON DELETE RESTRICT,
                    -- 默认2='user'（普通用户），见 001_roles.sql 预置数据
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email
    ON users (email)
    WHERE email IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_users_role_id
    ON users (role_id);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE users IS '用户表，支撑后续登录与多用户任务隔离';
COMMENT ON COLUMN users.password_hash IS '密码哈希（如bcrypt/argon2），不存明文';
