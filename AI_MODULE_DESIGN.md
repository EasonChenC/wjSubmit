# AI 模块设计实现文档

## 概述

在项目中成功设计并实现了一个可配置的 AI 模块，用于增强反向题识别的准确性。该模块允许在问卷分析时可选择使用 AI 来识别量表题中的正向题和反向题。

---

## 项目结构

```
project/
├── ai/                          # 新建：AI 模块（独立）
│   ├── __init__.py             # 模块导出
│   ├── config.py               # AI 配置管理（单例）
│   ├── client.py               # OpenAI 兼容 HTTP 客户端
│   └── reverse_detector.py      # AI 反向题检测逻辑
├── prompt/                      # 新建：提示词目录
│   └── reverse_item_detection.txt  # 反向题检测提示词
├── api/
│   ├── main.py                 # 修改：注册 AI 路由
│   ├── models.py               # 修改：添加 AI 相关数据模型
│   └── routers/
│       ├── ai.py               # 新建：AI 配置接口
│       ├── questionnaire.py     # 修改：analyze 支持 use_ai 参数
│       └── __init__.py          # 修改：导入 AI 路由
└── core/                        # 保持不变
    ├── reverse_item_detector.py
    ├── rule_based_analyzer.py
    └── ...
```

---

## 核心模块说明

### 1. AI 配置管理 (`ai/config.py`)

**AIConfigManager** - 单例模式管理全局 AI 配置

```python
manager = AIConfigManager.get_instance()

# 获取配置
config = manager.get_config()

# 更新配置
manager.update_config(
    api_key="sk-...",
    model="gpt-4o-mini",
    base_url="https://api.openai.com/v1",  # 支持自定义代理
    enabled=True
)

# 检查是否已配置
if manager.is_configured():
    # AI 已配置且启用
```

**特点**：
- 内存存储（暂无 DB，后续可扩展）
- 支持 OpenAI 兼容 API（官方、Azure、Ollama、中转代理等）
- 配置验证（API Key 非空且启用状态）

### 2. AI 客户端 (`ai/client.py`)

**AIClient** - 通用的 OpenAI 兼容 HTTP 客户端

```python
client = AIClient(
    api_key="sk-...",
    model="gpt-4o-mini",
    base_url="https://api.openai.com/v1"
)

# 发送聊天请求
response = await client.chat(
    messages=[{"role": "user", "content": "..."}],
    temperature=0.1
)

# 测试连接
success = await client.test_connection()
```

**特点**：
- 异步支持（使用 `httpx.AsyncClient`）
- 兼容所有 OpenAI 格式 API
- 支持自定义 base_url（代理、企业版等）
- 内置连接测试

### 3. AI 反向题检测 (`ai/reverse_detector.py`)

**override_schema_with_ai_detection** - 使用 AI 覆盖问卷架构中的反向题检测结果

```python
from ai.reverse_detector import override_schema_with_ai_detection

await override_schema_with_ai_detection(schema, ai_client)
# schema 被就地修改，反向题检测结果被 AI 结果覆盖
```

**工作流**：
1. 从 schema 中提取所有量表题（RATING/NPS/MATRIX）
2. 构建 JSON 格式的题目数据
3. 加载提示词模板（从 `prompt/reverse_item_detection.txt`）
4. 发送给 AI 进行分析
5. 解析 AI 返回的 JSON 结果
6. 就地更新 `schema.questions[*].metadata`：
   - `is_reverse`: 是否反向题
   - `reverse_confidence`: 置信度（AI 默认为 1.0）
   - `detection_method`: 检测方法标记为 `"ai"`
7. 更新 `schema.metadata['reverse_items']` 列表
8. 故障回退：如果 AI 请求失败，保留关键词检测结果并记录错误

### 4. 提示词设计 (`prompt/reverse_item_detection.txt`)

提示词使用中文，针对量表题特性设计：

```
你是问卷分析专家。请识别以下量表题中的正向题和反向题。

[题目 JSON 数据]

请返回 JSON 格式结果，只包含两个数组：
- forward_items: 正向题 id 列表
- reverse_items: 反向题 id 列表

返回格式：{"forward_items": ["q1"], "reverse_items": ["q2"]}
```

---

## API 接口说明

### AI 配置接口

#### GET `/api/ai/config`
获取当前 AI 配置（不返回 API Key 原文）

**Response:**
```json
{
  "success": true,
  "data": {
    "model": "gpt-4o-mini",
    "base_url": "https://api.openai.com/v1",
    "enabled": true,
    "has_api_key": true
  }
}
```

#### POST `/api/ai/config`
更新 AI 配置（只更新提供的字段）

**Request:**
```json
{
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1",
  "enabled": true
}
```

#### POST `/api/ai/test`
测试 AI 连接和认证

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "AI connection test passed successfully"
  }
}
```

### 问卷分析接口增强

#### POST `/api/questionnaire/analyze`
**新增参数**：`use_ai` (boolean)

**Request:**
```json
{
  "url": "https://v.wjx.cn/vm/eLeS3jD.aspx",
  "use_ai": true  // ← 新增，可选，默认 false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "...": "其他字段保持不变",
    "detection_method": "ai",  // ← 新增：显示使用了哪种检测方法
    "questions": [
      {
        "...": "其他字段",
        "is_reverse": true,
        "detection_method": "ai"  // ← 新增：每个问题标记检测来源
      }
    ]
  }
}
```

---

## 使用流程

### 前端用户流程

1. **配置 AI**
   - 打开"设置"面板
   - 输入 OpenAI API Key（或其他兼容服务）
   - 可选：修改模型名称、API 基础 URL
   - 点击"启用 AI"开关
   - 点击"测试连接"验证配置

2. **分析问卷**
   - 输入问卷 URL
   - **勾选**"使用 AI 识别反向题"
   - 点击"分析"
   - 等待分析完成
   - 查看问卷结构和反向题列表

3. **对比结果**
   - 列表中每个反向题旁显示"AI"或"关键词"标签
   - 用户可对比两种方法的结果

### 后端业务流程

```python
# 1. 用户配置 AI（已实现）
POST /api/ai/config
manager.update_config(api_key="...", enabled=True)

# 2. 用户测试连接（已实现）
POST /api/ai/test
client.test_connection()

# 3. 用户分析问卷带 use_ai=true（已实现）
POST /api/questionnaire/analyze
request.use_ai == True
  → 检查 AI 是否已配置
  → 创建 AIClient
  → 调用 override_schema_with_ai_detection
  → 返回 AI 检测结果
```

---

## 后续扩展预留

该 AI 模块设计为通用基础设施，支持未来其他功能复用：

- **Persona 生成** - 使用 AI 生成更逼真的用户角色
- **智能答案生成** - AI 根据问卷题意自动选择合适答案
- **问卷质量评估** - AI 识别低质量或恶意问卷
- **多语言支持** - 扩展提示词支持不同语言

所有这些功能都可以直接导入 `ai.client.AIClient` 和 `ai.config.AIConfigManager` 复用。

---

## 技术亮点

1. **架构解耦** - AI 模块独立于 core，不侵入现有代码逻辑
2. **故障回退** - AI 失败时自动保留关键词检测结果
3. **灵活配置** - 支持任何 OpenAI 兼容 API（官方/Azure/Ollama/中转）
4. **内存存储** - 暂无 DB，便于快速实现，后续可扩展到数据库
5. **可观测性** - 返回检测方法来源，便于用户理解结果来自何处

---

## 测试清单

- [x] AI 模块导入成功
- [x] 配置管理（单例模式）
- [x] HTTP 客户端连接测试
- [x] 提示词模板加载
- [x] API 路由注册
- [x] 数据模型验证

**后续需要通过完整集成测试验证**（需要有效的 API Key）

