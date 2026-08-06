# 前端对接文档 - AI 模块增强功能

## 📌 概览

后端新增了 AI 配置管理和智能量表题识别功能。前端需要在以下几个地方进行对接和UI调整。

---

## 🔷 模块一：AI 配置管理面板

### 1.1 新增页面/组件：AI 设置面板

**路由建议**：`/settings/ai` 或在现有设置中新增 AI 标签页

**UI 布局**：
```
┌─ AI 设置 ────────────────────────────┐
│                                      │
│ ☐ 启用 AI 识别（toggle switch）      │
│                                      │
│ API Key:                             │
│ [••••••••••••••] (密码框)             │
│ [Test Connection] 按钮               │
│                                      │
│ 模型名称：                           │
│ [gpt-4o-mini] (输入框)               │
│                                      │
│ API 基础 URL：                       │
│ [https://api.openai.com/v1] (输入框) │
│ 💡 支持自定义 URL（如代理）          │
│                                      │
│ [Save] [Cancel]                     │
└──────────────────────────────────────┘
```

### 1.2 API 接口对接

#### 获取当前 AI 配置
```javascript
// GET /api/ai/config
fetch('/api/ai/config')
  .then(r => r.json())
  .then(data => {
    // data.data = {
    //   model: "gpt-4o-mini",
    //   base_url: "https://api.openai.com/v1",
    //   enabled: true,
    //   has_api_key: true  ← 注意：不返回密钥原文
    // }
  })
```

#### 更新 AI 配置
```javascript
// POST /api/ai/config
const config = {
  api_key: "sk-xxx...",     // 仅当用户修改时发送
  model: "gpt-4o-mini",
  base_url: "https://api.openai.com/v1",
  enabled: true
};

fetch('/api/ai/config', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(config)
})
  .then(r => r.json())
  .then(data => {
    console.log('配置已保存');
    // 显示成功提示
  })
```

#### 测试连接
```javascript
// POST /api/ai/test
fetch('/api/ai/test', { method: 'POST' })
  .then(r => r.json())
  .then(data => {
    if (data.data.success) {
      showMessage('连接成功！');
    } else {
      showError(`连接失败：${data.data.message}`);
    }
  })
```

### 1.3 UI 交互逻辑

**API Key 输入框**：
- ✅ 密码类型（type="password"）
- ✅ 显示/隐藏切换按钮（👁 icon）
- ✅ 本地存储（localStorage）加密保存
- ✅ 为空时显示占位符："••••••••••••••"

**启用开关**：
- ✅ toggle 样式
- ✅ 关闭时，下面的输入框置灰或禁用
- ✅ 当 API Key 为空时，开关自动禁用

**Test Connection 按钮**：
- ✅ 点击后显示 loading 状态
- ✅ 成功 → 绿色勾 + "连接成功"
- ✅ 失败 → 红色叉 + 错误信息
- ✅ 禁用条件：API Key 为空或 enabled=false

**Save 按钮**：
- ✅ 点击后提交配置
- ✅ 显示 loading 状态
- ✅ 保存前验证：API Key 不为空（如果 enabled=true）
- ✅ 保存成功后显示 toast 消息

---

## 🔷 模块二：问卷分析页面增强

### 2.1 分析表单修改

**添加勾选框**：
```html
<form>
  <label>问卷 URL:</label>
  <input type="url" id="url" required />
  
  <!-- 新增 -->
  <label>
    <input type="checkbox" id="use_ai" />
    使用 AI 识别反向题（需先配置 AI）
  </label>
  
  <button type="submit">分析</button>
</form>
```

### 2.2 分析接口调用修改

**新增 use_ai 参数**：
```javascript
// POST /api/questionnaire/analyze
const request = {
  url: "https://v.wjx.cn/...",
  use_ai: document.getElementById('use_ai').checked  // ← 新增参数
};

fetch('/api/questionnaire/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(request)
})
  .then(r => r.json())
  .then(data => {
    // 处理新增字段
    console.log(data.data.detection_method);  // "ai" 或 "keyword"
  })
```

### 2.3 use_ai 勾选框的逻辑

**默认状态**：
- ✅ 默认不勾选（use_ai=false）
- ✅ 保持上次选择状态（localStorage）

**启用条件**：
- ✅ 仅当 AI 已配置且启用时，勾选框可用
- ✅ 若 AI 未配置，勾选框禁用 + 提示："请先在设置中配置 AI"
- ✅ 点击"设置 AI"链接，跳转到 AI 设置页面

**勾选框提示文本**：
```
☐ 使用 AI 识别反向题（需先配置 AI）
  💡 提示：启用后，系统将使用 AI 模型智能识别反向题和量表选项方向
```

---

## 🔷 模块三：分析结果展示增强

### 3.1 问题列表页面修改

**新增字段展示**：

#### 原有列表
```
题目ID | 题型 | 题干 | 是否必填 | 是否反向题 | 置信度
```

#### 新的列表结构
```
题目ID | 题型 | 题干 | 是量表题 | 反向题 | 检测方法 | 积极值 | 消极值
```

**具体列**：

| 列名 | 来源字段 | 展示规则 |
|------|---------|--------|
| 题目ID | `id` | 不变 |
| 题型 | `type` | 不变 |
| 题干 | `label` | 不变 |
| **是量表题** | `is_scale` | ✅ 新增，true/false → 是/否 |
| 反向题 | `is_reverse` | 仅在 is_scale=true 时显示 |
| **检测方法** | `detection_method` | ✅ 新增，显示 `ai` 或 `keyword` 标签 |
| **积极值** | `positive_values` | ✅ 新增，数组展示如 "[1,2]" |
| **消极值** | `negative_values` | ✅ 新增，数组展示如 "[4,5]" |

### 3.2 表格行示例

**radio 基础题（性别）**：
```
q1 | radio | 您的性别 | ❌ 否 | - | ai | - | -
```

**radio 量表题（满意度）**：
```
q20 | radio | 您对培训的满意度 | ✅ 是 | ❌ 否 | ai | [1,2] | [4,5]
```

**radio 反向量表题**：
```
q23 | radio | 您感到失望的程度 | ✅ 是 | ✅ 是 | ai | [4,5] | [1,2]
```

### 3.3 标签样式

**检测方法标签**：
- `ai` → 蓝色标签 "🤖 AI"
- `keyword` → 灰色标签 "📝 关键词"

**是否反向题**：
- ✅ → 绿色勾
- ❌ → 灰色叉
- `-` → 显示 "-"（不适用）

**是否量表题**：
- ✅ 是 → 绿色勾
- ❌ 否 → 灰色叉

### 3.4 交互：点击题目查看详情

点击任意行，展示详细信息面板：

```
┌─ 题目详情 ─────────────────────────┐
│ ID: q20                            │
│ 题型: radio                        │
│ 题干: 您对培训的满意度             │
│ 必填: ✅                            │
│ 是量表题: ✅ 是                     │
│ 反向题: ❌ 否                       │
│ 检测方法: 🤖 AI                    │
│                                    │
│ 选项列表:                          │
│ 1. 非常满意     [积极]            │
│ 2. 比较满意     [积极]            │
│ 3. 一般        [中立]             │
│ 4. 不太满意     [消极]            │
│ 5. 非常不满意   [消极]            │
│                                    │
│ AI 判断:                           │
│ positive_values: [1, 2]           │
│ negative_values: [4, 5]           │
│ neutral_values: [3]               │
└────────────────────────────────────┘
```

---

## 🔷 模块四：问卷提交流程（高信度模式）

### 4.1 提交配置表单修改

**现有表单**：
```
提交模式: ☑ 高信度模式
├─ 态度: ◉ 积极  ○ 消极
├─ 穿插变化: ☐ (checkbox)
└─ 变化比例: [0.05] (slider)
```

**新增说明文本**（仅在使用 AI 时显示）：
```
ℹ️ AI 已识别到 8 道量表题
  - 积极态度将优先选择"满意/同意"选项
  - 消极态度将优先选择"不满意/不同意"选项
```

### 4.2 提交时的数据流

```
用户选择 attitude="positive"
  ↓
系统调用 DynamicAnswerGenerator
  ↓
生成器检查每道量表题的 positive_values
  ↓
从 positive_values 中随机选择答案
  ↓
提交问卷
```

**前端无需修改**，只需显示提示文本

---

## 📋 前端对接清单

### 🟢 必须修改

- [ ] **AI 设置页面** - 新增 `/settings/ai` 或标签页
  - [x] API Key 输入框（密码类型）
  - [x] 模型名称输入框
  - [x] Base URL 输入框
  - [x] 启用/禁用开关
  - [x] Test Connection 按钮
  - [x] Save/Cancel 按钮

- [ ] **问卷分析表单** 
  - [x] 添加 use_ai 勾选框
  - [x] 条件显示（AI 未配置时禁用）
  - [ ] 跳转到 AI 设置的链接

- [ ] **分析结果表格** 
  - [x] 添加 is_scale 列
  - [x] 添加 detection_method 列（标签）
  - [x] 添加 positive_values 列
  - [x] 添加 negative_values 列
  - [x] 当 is_scale=false 时隐藏反向题、积极值、消极值列

- [ ] **详情面板** 
  - [x] 显示 AI 判断的 positive/negative/neutral_values
  - [x] 在选项列表中标记每个选项的分类

### 🟡 建议优化

- [ ] localStorage 保存 use_ai 用户偏好
- [ ] localStorage 加密保存 API Key（可选，需要安全评估）
- [ ] 分析进度条 + 实时反馈（特别是 AI 检测较慢时）
- [ ] 快捷链接：分析页面 → AI 配置（当 AI 未配置时）
- [ ] 分析结果导出为 Excel 时，包含新字段

### 🔵 可选增强

- [ ] 检测方法字段可视化：饼图显示 AI vs Keyword 比例
- [ ] 热力图：哪些题目 AI 识别为量表题
- [ ] 对比视图：AI 结果 vs 关键词检测结果（调试用）

---

## 🔗 API 接口速查表

### AI 配置接口

```javascript
// 获取配置
GET /api/ai/config

// 更新配置
POST /api/ai/config
{
  "api_key": "sk-...",
  "model": "gpt-4o-mini",
  "base_url": "https://api.openai.com/v1",
  "enabled": true
}

// 测试连接
POST /api/ai/test
```

### 问卷分析接口（修改）

```javascript
// 新增 use_ai 参数
POST /api/questionnaire/analyze
{
  "url": "https://v.wjx.cn/...",
  "use_ai": true  // ← 新增
}

// 响应新增字段
{
  "data": {
    "detection_method": "ai",  // 或 "keyword"
    "questions": [
      {
        "id": "q20",
        "is_scale": true,       // ← 新增
        "is_reverse": false,
        "detection_method": "ai",  // ← 新增
        "positive_values": ["1", "2"],  // ← 新增
        "negative_values": ["4", "5"]   // ← 新增
      }
    ]
  }
}
```

---

## 💬 用户交互流程

### 场景 1：首次使用 AI 识别

```
用户进入分析页面
  ↓
看到 "使用 AI 识别反向题" 勾选框，但被禁用
  ↓
点击提示中的"设置 AI"链接
  ↓
跳转到 AI 设置页面
  ↓
输入 API Key、模型、URL
  ↓
点击 "Test Connection" → 成功
  ↓
点击 Save
  ↓
返回分析页面（或自动返回）
  ↓
勾选框已启用
  ↓
勾选 use_ai，点击分析
  ↓
看到 detection_method="ai" 的结果
```

### 场景 2：分析结果中的量表题识别

```
用户看到问题列表
  ↓
radio 题型的问题分为两类：
  - q1-q5（是量表题=否）← 基础信息题
  - q15-q25（是量表题=是）← 量表题
  ↓
对于量表题，显示 positive/negative 值
  ↓
用户可点击查看详细信息
```

---

## ⚠️ 注意事项

### 安全性

- [ ] **API Key 不传输到前端**：仅在浏览器 localStorage 存储，不上传日志或分析
- [ ] **HTTPS 必需**：涉及 API Key 操作必须走 HTTPS
- [ ] **密码框类型**：API Key 输入使用 `type="password"`
- [ ] **不显示完整 Key**：has_api_key=true 时仅显示"已配置"，不显示密钥内容

### 性能

- [ ] **缓存分析结果**：use_ai=true 的分析结果可缓存，避免重复请求
- [ ] **加载指示**：AI 检测通常较慢（10-30s），显示进度或 loading 状态
- [ ] **超时处理**：设置合理的超时时间（如 60s）

### 兼容性

- [ ] **Fallback**：use_ai=false 时保持原有流程
- [ ] **渐进增强**：新字段（positive_values 等）为可选，缺失时不破坏 UI
- [ ] **浏览器兼容**：支持 localStorage、fetch、async/await 的现代浏览器

---

## 📞 常见问题

### Q: use_ai 勾选框什么时候禁用？
**A**: 
- AI 未配置时（has_api_key=false）
- AI 未启用时（enabled=false）
- 网络错误或配置无效时

### Q: positive_values 和 negative_values 为空时怎么办？
**A**: 
- 仅在非 AI 检测或 is_scale=false 时为空
- 不显示这两列（或显示 "-"）
- 答题生成器自动 fallback 到旧逻辑

### Q: 提交时，系统怎样使用 positive/negative 值？
**A**: 
- 后端在 DynamicAnswerGenerator 中处理
- 前端无需改动，automatic 使用这些值

### Q: 能同时用 AI 和关键词检测吗？
**A**: 不能。use_ai=true 时 AI 检测覆盖关键词检测结果。

---

## 🎨 UI 设计参考

### AI 设置面板样式建议

使用现有设计系统的：
- 输入框、按钮、开关、标签
- 颜色主题（brand color）
- 响应式布局（mobile-friendly）

### 表格新增列的宽度建议

| 列名 | 宽度 | 对齐 |
|------|------|------|
| 是量表题 | 80px | 中 |
| 反向题 | 80px | 中 |
| 检测方法 | 100px | 左 |
| 积极值 | 100px | 左 |
| 消极值 | 100px | 左 |

---

完整对接文档已完成！如有疑问，请参考后端 API 文档或联系后端团队。
