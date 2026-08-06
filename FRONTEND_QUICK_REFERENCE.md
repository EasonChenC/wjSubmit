# 前端对接 - 快速参考卡

## 🎯 核心修改清单（优先级）

### P0 - 必做（影响主流程）

#### 1. AI 设置页面（新建）
- 路由：`/settings/ai`
- 字段：API Key、模型、Base URL、启用开关
- 按钮：Test Connection、Save、Cancel
- API：`GET/POST /api/ai/config`、`POST /api/ai/test`

#### 2. 分析表单修改
- 添加：use_ai 勾选框
- 逻辑：use_ai=true 时，后端使用 AI 检测
- API：`POST /api/questionnaire/analyze` 新增 use_ai 参数

#### 3. 分析结果表格修改
- 新增列：is_scale、detection_method、positive_values、negative_values
- 显示规则：is_scale=false 时隐藏相关列
- 检测方法显示为标签（🤖 AI / 📝 Keyword）

---

## 📊 响应数据示例

### 获取 AI 配置
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

### 分析结果（新增字段）
```json
{
  "success": true,
  "data": {
    "detection_method": "ai",
    "scale_questions": 12,
    "questions": [
      {
        "id": "q20",
        "type": "radio",
        "label": "您对培训的满意度",
        "is_scale": true,           // ✨ 新增
        "is_reverse": false,
        "detection_method": "ai",    // ✨ 新增
        "positive_values": ["1", "2"],   // ✨ 新增
        "negative_values": ["4", "5"]    // ✨ 新增
      }
    ]
  }
}
```

---

## 🖼️ UI 组件变更

### 表格列显示规则

| 列名 | 显示条件 | 样式 |
|------|---------|------|
| is_scale | 总是显示 | true→✅ / false→❌ |
| is_reverse | is_scale=true | true→✅ / false→❌ |
| detection_method | is_scale=true | ai→🤖蓝 / keyword→📝灰 |
| positive_values | is_scale=true | [1,2] 格式 |
| negative_values | is_scale=true | [4,5] 格式 |

### use_ai 勾选框禁用条件

```javascript
disabled = !has_api_key || !ai_enabled
tooltip = "请先在设置中配置 AI"  // 当 disabled=true 时显示
```

---

## 🔌 API 调用代码片段

### 保存 AI 配置
```javascript
async function saveAIConfig(config) {
  const res = await fetch('/api/ai/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      api_key: config.apiKey,
      model: config.model,
      base_url: config.baseUrl,
      enabled: config.enabled
    })
  });
  return res.json();
}
```

### 分析问卷（使用 AI）
```javascript
async function analyzeQuestionnaire(url, useAI) {
  const res = await fetch('/api/questionnaire/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url, use_ai: useAI })
  });
  return res.json();
}
```

### 测试 AI 连接
```javascript
async function testAIConnection() {
  const res = await fetch('/api/ai/test', { method: 'POST' });
  const data = await res.json();
  return data.data.success;  // true/false
}
```

---

## 📝 HTML 示例

### AI 设置表单
```html
<form id="ai-form">
  <label>
    <input type="checkbox" id="ai-enabled" /> 启用 AI
  </label>
  
  <label>API Key:
    <input type="password" id="api-key" />
  </label>
  
  <label>模型:
    <input type="text" id="model" value="gpt-4o-mini" />
  </label>
  
  <label>Base URL:
    <input type="text" id="base-url" value="https://api.openai.com/v1" />
  </label>
  
  <button type="button" onclick="testConnection()">Test Connection</button>
  <button type="submit">Save</button>
</form>
```

### 分析表单（use_ai 勾选框）
```html
<form id="analyze-form">
  <input type="url" id="url" required />
  
  <label>
    <input type="checkbox" id="use-ai" />
    使用 AI 识别反向题
    <span class="hint">需先配置 AI</span>
  </label>
  
  <button type="submit">分析</button>
</form>
```

---

## ⏱️ 时间估算

| 任务 | 工时 |
|------|------|
| AI 设置页面 | 4-6h |
| 分析表单修改 | 1-2h |
| 表格新增列 | 2-3h |
| 详情面板修改 | 2-3h |
| 测试 & 调试 | 3-4h |
| **总计** | **12-18h** |

---

## ⚡ 快速开始

### 第 1 步：添加 AI 设置路由
- 新建 `/settings/ai` 页面
- 调用 `GET /api/ai/config` 初始化表单

### 第 2 步：添加 use_ai 参数
- 分析表单中添加勾选框
- 修改 analyze 调用，传入 use_ai 参数

### 第 3 步：表格显示新字段
- 添加 4 个新列
- 根据 is_scale 显示/隐藏对应内容

### 第 4 步：测试
- 配置有效 API Key
- 勾选 use_ai，验证响应中的新字段

---

## 🔒 安全检查清单

- [ ] API Key 使用 password 类型输入框
- [ ] 不在日志/console 中打印 API Key
- [ ] localStorage 存储 API Key 时加密（可选）
- [ ] has_api_key=true 时不显示密钥内容
- [ ] HTTPS 传输 API Key

---

## 🐛 常见问题排查

**Q: 勾选框被禁用**  
A: 检查 has_api_key 和 enabled 字段，都需要为 true

**Q: 新增列显示为空**  
A: 检查响应中 is_scale 是否为 true，且 positive/negative_values 是否存在

**Q: Test Connection 超时**  
A: 增加超时时间，或检查网络/API Key 是否有效

---

完成上述清单后，即可实现完整的 AI 增强功能！
