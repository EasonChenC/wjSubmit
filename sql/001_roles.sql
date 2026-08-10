-- 001_roles.sql
-- 角色表
-- 用途：为用户表提供角色归属（如 admin / user），支撑后续的权限区分
-- （例如限制普通用户的批量提交份数，或只允许管理员修改全局AI配置）。

CREATE TABLE IF NOT EXISTS roles (
    id              SMALLSERIAL PRIMARY KEY,
    code            VARCHAR(32) NOT NULL,           -- 角色标识，如 'admin' / 'user'
    name            VARCHAR(64) NOT NULL,           -- 角色展示名，如 '管理员' / '普通用户'
    description     VARCHAR(255),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_roles_code UNIQUE (code)
);

CREATE TRIGGER trg_roles_updated_at
    BEFORE UPDATE ON roles
    FOR EACH ROW
    EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE roles IS '角色表，用户通过 users.role_id 关联到具体角色';

-- 预置基础角色
INSERT INTO roles (code, name, description) VALUES
    ('admin', '管理员', '拥有全局配置和所有任务的管理权限'),
    ('user',  '普通用户', '可创建和管理自己的问卷任务')
ON CONFLICT (code) DO NOTHING;
