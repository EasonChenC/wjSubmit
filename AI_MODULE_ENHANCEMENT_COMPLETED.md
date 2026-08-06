# AI 模块增强设计 - 实现完成

## 📋 完成的修改

所有 5 个核心文件已成功修改，支持更智能的量表题识别和答题逻辑。

---

## 🔄 核心变更说明

### 1. AI 数据流增强（包含 radio + 选项）

**传入 AI 的数据** 现在包括：
- ✅ **所有题型**：rating + nps + matrix + **radio**
- ✅ **完整选项**：`{"value": "1", "label": "非常满意"}` 格式
- ✅ **统一结构**：所有题型都统一为 `[{value, label, ...}]` 格式

**之前的问题**：
```json
// 旧：只有量表题，无选项，无法判断方向
[{"id": "q1", "label": "...", "type": "rating"}]
```

**现在的改进**：
```json
// 新：包含radio，有完整选项，AI可判断方向
[
  {
    "id": "q15",
    "type": "radio",
    "label": "*15.您对义警培训的满意度",
    "options": [
      {"value": "1", "label": "非常满意"},
      {"value": "2", "label": "比较满意"},
      {"value": "3", "label": "一般"},
      {"value": "4", "label": "不太满意"},
      {"value": "5", "label": "非常不满意"}
    ]
  }
]
```

---

### 2. AI 返回结构重新设计

**旧返回格式**（二分类）：
```json
{
  "forward_items": ["q1", "q3"],
  "reverse_items": ["q2"]
}
```

**新返回格式**（包含选项方向）：
```json
{
  "scale_items": [
    {
      "id": "q15",
      "is_reverse": false,
      "positive_values": ["1", "2"],
      "negative_values": ["4", "5"],
      "neutral_values": ["3"]
    }
  ],
  "non_scale_ids": ["q1", "q2", "q3"]
}
```

**关键改进**：
- ✅ AI 识别 radio 是否为量表题（`non_scale_ids` 列表）
- ✅ AI 判断正向/反向题（`is_reverse` 字段）
- ✅ AI 直接标记选项方向（`positive_values` / `negative_values`）
- ✅ 无需再依赖"高分=积极"的错误假设

---

### 3. 提示词重写（三大任务）

`prompt/reverse_item_detection.txt` 现在包含：

| 任务 | 说明 |
|------|------|
| **识别量表题** | 区分量表题（连续程度测量）vs 基础题（分类信息） |
| **识别正向/反向** | 判断题干表述方向 |
| **识别选项方向** | 根据选项 label 判断哪些代表积极/消极，不靠位置 |

**关键指引**：
```
"非常满意,比较满意,一般,不太满意,非常不满意"
→ positive=[1,2], neutral=[3], negative=[4,5]

但如果选项反序：
"非常不满意,不太满意,一般,比较满意,非常满意"
→ positive=[4,5], neutral=[3], negative=[1,2]
```

---

### 4. API 数据模型更新

**QuestionResponse** 新增字段：
```python
positive_values: Optional[List[str]]  # 积极选项值
negative_values: Optional[List[str]]  # 消极选项值
```

**AnalyzeResponse** 新增字段：
```python
detection_method: str  # "keyword" or "ai"
```

---

### 5. 问卷分析接口增强

**修改点**：
- ✅ `is_scale` 判断加入 `metadata.get('is_scale')` 分支（支持 AI 识别的 radio 量表题）
- ✅ 每道量表题返回 `positive_values` / `negative_values`
- ✅ scale_questions 计数包含 AI 识别的 radio 量表题

```python
# 旧逻辑
is_scale = question.type in [RATING, NPS, MATRIX]

# 新逻辑
is_scale = question.type in [RATING, NPS, MATRIX] or question.metadata.get('is_scale', False)
```

---

### 6. 答题生成器智能化

**DynamicAnswerGenerator** 更新：

#### 6.1 量表题识别更新
```python
def _is_scale_question(self):
    # 检查硬编码类型
    if question.type in [RATING, NPS, MATRIX]:
        return True
    # 检查 AI 识别（radio 量表题）
    if question.metadata.get('is_scale', False):
        return True
    return False
```

#### 6.2 答题逻辑核心改进
```python
def _generate_scale_answer_with_attitude(self, question):
    # 优先使用 AI 返回的值
    positive_values = question.metadata.get('positive_values', [])
    negative_values = question.metadata.get('negative_values', [])
    
    if attitude == "positive":
        return random.choice(positive_values)  # 从积极选项中选
    else:
        return random.choice(negative_values)  # 从消极选项中选
    
    # Fallback：原有的高分/低分逻辑（不含 AI 数据时）
```

**关键优势**：
- ✅ 不再假设"高分=积极"
- ✅ 直接使用 AI 标记的选项值
- ✅ radio 量表题也能根据 attitude 正确选择
- ✅ 无需反向计分复杂逻辑

---

## 🎯 效果示意

### 场景：用户选择 attitude=positive，分析一份包含这个 radio 题的问卷

```
题目 q20: "您对义警培训的满意度"
选项：非常满意(1) 比较满意(2) 一般(3) 不太满意(4) 非常不满意(5)

旧逻辑问题：
- radio 题被忽略，当做基础题，随机选择
- 可能选到 value=5（非常不满意），与 attitude=positive 矛盾

新逻辑：
1. AI 识别为量表题 → is_scale=true
2. AI 标记 positive_values=["1", "2"]
3. 生成器看到 attitude=positive → 从 ["1", "2"] 中随机选
4. 答案为 value=1 或 2（满意）✅ 与 attitude 一致
```

---

## 📊 端到端流程

```
用户请求 POST /api/questionnaire/analyze?use_ai=true
    ↓
RuleBasedAnalyzer 解析问卷结构
    ↓
AI检测器收集所有题目（radio+rating+matrix+nps）
    ↓
规范化选项格式 → 发送给 AI
    ↓
AI 返回：
  - 哪些 radio 是量表题
  - 每道题的正向/反向
  - 每道题的 positive_values/negative_values
    ↓
更新 schema.metadata：
  - question.metadata['is_scale']
  - question.metadata['positive_values']
  - question.metadata['negative_values']
    ↓
API 响应：
  - is_scale=true/false
  - positive_values/negative_values
  - detection_method='ai'
    ↓
后续提交时，DynamicAnswerGenerator 根据 attitude 和这些值生成答案
```

---

## 🔗 文件修改清单

| 文件 | 修改内容 |
|------|---------|
| `prompt/reverse_item_detection.txt` | 重写提示词，三大任务+新返回格式 |
| `ai/reverse_detector.py` | 扩展数据收集+新返回格式解析+metadata更新 |
| `api/models.py` | QuestionResponse 增加 positive/negative_values 字段 |
| `api/routers/questionnaire.py` | is_scale 判断+新字段传递 |
| `core/dynamic_answer_generator.py` | 量表题识别+答题逻辑更新 |

---

## ✨ 核心优势

1. **准确性↑**：AI 看选项而不是猜测，识别准确度大幅提升
2. **灵活性↑**：支持任意顺序的选项（不依赖位置）
3. **一致性↑**：attitude 与实际答案完全对应
4. **扩展性↑**：radio 量表题也能正确处理

---

## 🚀 后续使用

### 调用示例

```bash
curl -X POST http://localhost:8000/api/questionnaire/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://...", "use_ai": true}'
```

### 响应中的新字段

```json
{
  "data": {
    "questions": [
      {
        "id": "q20",
        "type": "radio",
        "is_scale": true,
        "is_reverse": false,
        "positive_values": ["1", "2"],
        "negative_values": ["4", "5"],
        "detection_method": "ai"
      }
    ]
  }
}
```

### 后续提交

```bash
curl -X POST http://localhost:8000/api/questionnaire/submit \
  -d '{
    "url": "https://...",
    "count": 5,
    "mode": "high_reliability",
    "config": {
      "attitude": "positive"  # ← 基于这个，生成器使用 positive_values
    }
  }'
```

---

## ⚙️ 技术特点

- ✅ **向后兼容**：无 AI 数据时自动 fallback 到原有逻辑
- ✅ **渐进式部署**：旧题型（rating/nps/matrix）不受影响
- ✅ **灵活容错**：AI 失败不会破坏答题
- ✅ **数据驱动**：所有逻辑由 AI 结果驱动，无硬编码假设

---

## 验证状态

✅ 所有修改通过 Python 语法验证
✅ 所有导入正常
✅ 代码风格保持一致
✅ 无依赖冲突

系统已准备就绪，可进行完整集成测试！
