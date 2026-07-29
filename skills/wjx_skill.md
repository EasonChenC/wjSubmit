# 问卷星自动化填写 - AI 智能适配指南

## 文档目的

本文档为 AI 提供问卷自动化填写的完整知识库，用于：
1. 识别不同问卷中的题型
2. 生成对应的选择器代码
3. 生成智能答案生成器
4. 适配新问卷的自动化填写

---

## 一、问卷星题型识别与选择器模式

### 1.1 单选题 (Single Choice / Radio)

**识别特征：**
- HTML: `<input type="radio">` 元素（隐藏）
- UI框架: jQuery Mobile，显示为 `.jqradio` 自定义样式
- 每个选项有唯一 ID，格式 `q{题号}_{选项编号}`
- 关键标识: `<div class="ui-radio">`

**移动版选择器模板：**
```python
await page.click(f'.label[for="q{question_num}_{answer}"]')
```

**代码示例：**
```python
# Q1: 性别（单选题，选项1=男，2=女，3=其他）
if q_id == 'q1':
    await page.click(f'.label[for="q1_{answer}"]')
```

**答案生成模式：**
```python
# 基础随机选择
answers['q1'] = random.randint(1, 3)

# 带权重的随机选择（模拟真实分布）
answers['q1'] = random.choices(
    [1, 2, 3],  # 选项值
    weights=[0.48, 0.48, 0.04]  # 权重：男48%，女48%，其他4%
)[0]
```

**注意事项：**
- ⚠️ 不要直接点击隐藏的 `<input>` 元素（会超时）
- ✅ 必须点击 `.label[for="..."]` 元素才能触发选中

---

### 1.2 多选题 (Multiple Choice / Checkbox)

**识别特征：**
- HTML: `<input type="checkbox">` 元素（隐藏）
- UI框架: jQuery Mobile，显示为 `.jqcheck` 自定义样式
- 每个选项有唯一 ID，格式 `q{题号}_{选项编号}`
- 关键标识: `<div class="ui-checkbox">`
- 可能包含"其他"选项，带文本输入框 `#tqq{题号}_{选项编号}`

**移动版选择器模板：**
```python
# 多选主选项
if isinstance(answer, list):
    for option in answer:
        await page.click(f'.label[for="q{question_num}_{option}"]')

# "其他"选项的文本框
if 'tqq{question_num}_{other_option}' in answers:
    await page.fill(f'#tqq{question_num}_{other_option}', text_answer)
```

**代码示例：**
```python
# Q6: 信息渠道（多选题，7个选项）
if q_id == 'q6':
    if isinstance(answer, list):
        for option in answer:
            await page.click(f'.label[for="q6_{option}"]')

# Q9: 购物平台（多选题，8个选项，第8项是"其他"）
if q_id == 'q9':
    if isinstance(answer, list):
        for option in answer:
            await page.click(f'.label[for="q9_{option}"]')

# Q9-1: 其他平台文本框
if q_id == 'tqq9_8':
    await page.fill('#tqq9_8', answer)
```

**答案生成模式：**
```python
# 随机选择2-4个选项（不含"其他"）
answers['q6'] = random.sample(range(1, 8), k=random.randint(2, 4))

# 随机选择1-4个选项（可能包含"其他"）
selected = random.sample(range(1, 9), k=random.randint(1, 4))
answers['q9'] = selected

# 如果选择了"其他"（选项8），生成文本
if 8 in selected:
    other_platforms = ['拼多多', '唯品会', '小红书', '抖音商城', '快手小店']
    answers['tqq9_8'] = random.choice(other_platforms)
```

**注意事项：**
- ⚠️ 不要使用 `page.check()` 方法（对隐藏元素无效）
- ✅ 必须使用 `page.click()` 点击 `.label` 元素
- ✅ "其他"选项的文本框使用 ID 选择器 `#tqq{题号}_{选项}`

---

### 1.3 下拉选择题 (Dropdown / Select)

**识别特征：**
- HTML: 原生 `<select>` 元素
- 可能使用 Select2 插件美化UI，但底层仍是 `<select>`
- 选项使用 `<option value="值">` 结构
- 通常第一个选项是 `value="-2"` 的"请选择"占位符

**移动版选择器模板：**
```python
await page.select_option('select[name="q{question_num}"]', str(answer))
```

**代码示例：**
```python
# Q2: 年龄（下拉选择，选项1-5）
if q_id == 'q2':
    await page.select_option('select[name="q2"]', str(answer))
```

**答案生成模式：**
```python
# 随机选择（排除占位符 -2）
answers['q2'] = random.randint(1, 5)

# 带权重的随机选择
answers['q2'] = random.choices(
    [1, 2, 3, 4, 5],  # 18岁以下, 18-25, 26-35, 36-50, 50以上
    weights=[0.05, 0.30, 0.35, 0.20, 0.10]
)[0]
```

**注意事项：**
- ✅ 原生 `<select>` 元素可以直接使用 `select_option()` 方法
- ✅ 传入的值必须是字符串类型 `str(answer)`

---

### 1.4 文本输入题 (Text Input)

**识别特征：**
- HTML: `<input type="text">` 元素
- 可能包含 `readonly` 属性（如城市选择器）
- 通常有 `id` 和 `name` 属性

**移动版选择器模板：**
```python
# 普通文本输入
await page.fill('#q{question_num}', answer)

# 只读文本输入（需要用 JavaScript 绕过）
await page.evaluate(f'document.getElementById("q{question_num}").value = "{answer}"')
```

**代码示例：**
```python
# Q3: 城市（只读输入框，点击后打开城市选择器）
if q_id == 'q3':
    await page.evaluate(f'document.getElementById("q3").value = "{answer}"')

# Q13: 商品类别（普通文本输入）
if q_id == 'q13':
    await page.fill('#q13', answer)
```

**答案生成模式：**
```python
# 从预定义列表中随机选择
cities = ['北京市', '上海市', '深圳市', '广州市', '杭州市', '成都市']
answers['q3'] = random.choice(cities)

categories = ['服装鞋包', '数码家电', '美妆护肤', '食品饮料', '图书文具', '家居用品']
answers['q13'] = random.choice(categories)
```

**注意事项：**
- ⚠️ 如果输入框有 `readonly` 属性，`page.fill()` 会失败
- ✅ 对只读输入框使用 JavaScript 设置 `value` 属性

---

### 1.5 多行文本题 (Textarea)

**识别特征：**
- HTML: `<textarea>` 元素
- 通常用于开放性问题、建议、评论等
- 可能是可选填写项

**移动版选择器模板：**
```python
if answer:  # 检查是否有内容
    await page.fill('textarea#q{question_num}', answer)
```

**代码示例：**
```python
# Q14: 改进建议（多行文本）
if q_id == 'q14':
    if answer:  # 只在有内容时填写
        await page.fill('textarea#q14', answer)
```

**答案生成模式：**
```python
# 80%概率填写，20%概率留空
if random.random() < 0.8:
    suggestions = [
        '商品描述准确，收到的东西和图片一致。',
        '物流速度快，包装完好，商品质量满意。',
        '希望增加更多优惠活动，价格更实惠一些。',
        '客服态度很好，售后服务到位，很满意。',
        '商品种类丰富，购物体验不错，会继续光顾。'
    ]
    answers['q14'] = random.choice(suggestions)
else:
    answers['q14'] = ''  # 留空
```

**注意事项：**
- ✅ 多行文本通常是可选项，可以留空
- ✅ 生成的文本应该自然、符合语境

---

### 1.6 矩阵评分题 (Matrix Rating)

**识别特征：**
- HTML: 表格结构 `<table>` 或 `<tr>` 包含多行评分
- 每行有隐藏的 `<input type="text">` 字段，ID 格式 `q{题号}_{行索引}`
- UI: 点击评分元素 `<a class="rate-off" dval="分数">`
- 每行独立评分，通常1-5分或1-7分
- 行标识: `<tr fid="q{题号}_{行索引}">`

**移动版选择器模板：**
```python
# q{题号}_{行索引}，如 q7_0, q7_1, q7_2...
if q_id.startswith('q{question_num}_'):
    row_index = q_id.split('_')[1]
    await page.click(f'tr[fid="{q_id}"] a[dval="{answer}"]')
```

**代码示例：**
```python
# Q7: 购买因素矩阵（6行，每行1-5分）
# q7_0: 商品价格
# q7_1: 商品质量
# q7_2: 品牌知名度
# q7_3: 用户评价
# q7_4: 优惠促销
# q7_5: 物流服务
if q_id.startswith('q7_'):
    row_index = q_id.split('_')[1]
    await page.click(f'tr[fid="{q_id}"] a[dval="{answer}"]')
```

**答案生成模式：**
```python
# 每行独立生成评分
for i in range(6):
    answers[f'q7_{i}'] = str(random.randint(3, 5))  # 倾向于3-5分（正面评价）
```

**注意事项：**
- ⚠️ 不要直接填写隐藏的 `<input>` 字段
- ✅ 必须点击 `<a dval="分数">` 元素来触发评分
- ✅ 答案需要转换为字符串 `str(answer)`

---

### 1.7 评分题 (Rating / Star Rating)

**识别特征：**
- HTML: `<ul>` 包含多个 `<a class="rate-off">` 元素
- 隐藏字段: `<input type="hidden" id="q{题号}">`
- UI: 点击评分元素更新隐藏字段
- 评分范围: 通常1-5分（星级）或1-10分
- 容器ID: `#div{题号}`

**移动版选择器模板：**
```python
# 1-5分评分
await page.click(f'#div{question_num} a.rate-off[val="{answer}"]')
```

**代码示例：**
```python
# Q10: 满意度评分（1-5分）
if q_id == 'q10':
    await page.click(f'#div10 a.rate-off[val="{answer}"]')
```

**答案生成模式：**
```python
# 随机生成（倾向于高分）
answers['q10'] = random.randint(3, 5)

# 带权重的随机生成
answers['q10'] = random.choices(
    [1, 2, 3, 4, 5],
    weights=[0.02, 0.05, 0.15, 0.38, 0.40]  # 倾向于4-5分（满意/非常满意）
)[0]
```

**注意事项：**
- ✅ `val` 属性值与实际分数一致（1-5对应1-5分）
- ✅ 容器ID格式为 `#div{题号}`

---

### 1.8 NPS 推荐度评分 (NPS Rating)

**识别特征：**
- HTML: `<ul class="modlen11 onscore">` 包含11个评分元素
- 评分范围: 0-10分
- 隐藏字段: `<input type="hidden" id="q{题号}">`
- **特殊性**: `val` 属性从 1-11 对应分数 0-10

**移动版选择器模板：**
```python
# 注意：val = 实际分数 + 1
await page.click(f'#div{question_num} a.rate-off[val="{answer + 1}"]')
```

**代码示例：**
```python
# Q11: NPS推荐度（0-10分）
if q_id == 'q11':
    await page.click(f'#div11 a.rate-off[val="{answer + 1}"]')
```

**答案生成模式：**
```python
# 随机生成（倾向于推荐）
answers['q11'] = random.randint(7, 10)  # 7-10分为推荐者

# 带权重的随机生成（符合NPS分布）
answers['q11'] = random.choices(
    list(range(11)),  # 0-10分
    weights=[0.02, 0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.15, 0.10]
)[0]
```

**注意事项：**
- ⚠️ **关键**: `val` 属性比实际分数大1，必须使用 `answer + 1`
- ✅ 分数0对应 `val="1"`，分数10对应 `val="11"`

---

### 1.9 排序题 (Sorting / Ranking)

**识别特征：**
- HTML: `<ul>` 包含多个 `<li class="ui-li-static">` 元素
- 每个选项有 `serial` 属性，标识原始序号
- 隐藏字段: 多个 `<input type="hidden" id="q{题号}_{serial}">`
- 交互方式: 依次点击 `<li>` 元素完成排序
- 容器ID: `#div{题号}`

**移动版选择器模板：**
```python
# answer 是一个列表，表示点击顺序
if isinstance(answer, list) and len(answer) == {选项数量}:
    for option_value in answer:
        await page.click(f'#div{question_num} li.ui-li-static[serial="{option_value}"]')
        await asyncio.sleep(0.4)  # 每次点击后等待400ms
```

**代码示例：**
```python
# Q12: 促销方式排序（6个选项）
# serial 1-6: 直接降价、满减优惠、买赠活动、积分兑换、限时秒杀、会员专享
if q_id == 'q12':
    if isinstance(answer, list) and len(answer) == 6:
        for option_value in answer:
            await page.click(f'#div12 li.ui-li-static[serial="{option_value}"]')
            await asyncio.sleep(0.4)
```

**答案生成模式：**
```python
# 完全随机排序
answers['q12'] = list(range(1, 7))  # [1, 2, 3, 4, 5, 6]
random.shuffle(answers['q12'])      # 打乱顺序，如 [3, 1, 5, 2, 6, 4]

# 带权重的排序（某些选项更可能排前面）
# 方法：为每个选项生成随机分数，按分数排序
scores = {
    1: random.random() * 2.0,  # 直接降价：高权重
    2: random.random() * 1.5,  # 满减优惠：中高权重
    3: random.random() * 1.0,  # 买赠活动：中等权重
    4: random.random() * 0.8,  # 积分兑换：较低权重
    5: random.random() * 1.8,  # 限时秒杀：高权重
    6: random.random() * 1.2,  # 会员专享：中等权重
}
answers['q12'] = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
```

**注意事项：**
- ✅ 必须点击所有选项，确保列表长度匹配
- ✅ 每次点击后需要等待（建议400ms），让UI更新
- ✅ 点击顺序决定排序结果（第1次点击的排第1）

---

## 二、答案生成器核心模式

### 2.1 基础结构

```python
import random
from datetime import datetime

class AnswerGenerator:
    """智能答案生成器基类"""

    def generate_answers(self, constraints: dict = None) -> dict:
        """生成所有问题的答案

        Args:
            constraints: 约束条件，如 {'q1': 1} 表示强制 q1=1

        Returns:
            答案字典，如 {'q1': 2, 'q2': 3, ...}
        """
        answers = {}

        # 应用约束条件
        if constraints:
            answers.update(constraints)

        # 生成各题答案（调用具体题型方法）
        if 'q1' not in answers:
            answers['q1'] = self._generate_q1()
        if 'q2' not in answers:
            answers['q2'] = self._generate_q2()
        # ... 依此类推

        return answers

    def _generate_q1(self):
        """生成Q1答案（单选题）"""
        return random.choices([1, 2, 3], weights=[0.48, 0.48, 0.04])[0]

    def add_timing_data(self, answers: dict) -> dict:
        """添加时间数据，模拟真实用户行为"""
        answers['_timing'] = {
            'start_time': random.uniform(2, 5),  # 初始停留时间
            'answer_times': {}  # 每题停留时间
        }

        for q_id in answers:
            if q_id.startswith('q'):
                # 根据题型设置不同的停留时间
                if q_id in ['q1', 'q2', 'q4', 'q5', 'q8']:
                    # 单选题: 1-3秒
                    answers['_timing']['answer_times'][q_id] = random.uniform(1, 3)
                elif q_id in ['q6', 'q9']:
                    # 多选题: 2-5秒
                    answers['_timing']['answer_times'][q_id] = random.uniform(2, 5)
                elif q_id == 'q12':
                    # 排序题: 5-10秒
                    answers['_timing']['answer_times'][q_id] = random.uniform(5, 10)
                elif q_id in ['q13', 'q14']:
                    # 文本输入: 3-8秒
                    answers['_timing']['answer_times'][q_id] = random.uniform(3, 8)
                else:
                    # 其他题型: 2-4秒
                    answers['_timing']['answer_times'][q_id] = random.uniform(2, 4)

        return answers
```

### 2.2 答案生成策略

#### 策略1: 完全随机
```python
# 适用于测试、初期开发
answers['q1'] = random.randint(1, 3)
answers['q6'] = random.sample(range(1, 8), k=random.randint(2, 4))
```

#### 策略2: 带权重的随机（推荐）
```python
# 模拟真实用户分布
answers['q1'] = random.choices([1, 2, 3], weights=[0.48, 0.48, 0.04])[0]
answers['q10'] = random.choices([1, 2, 3, 4, 5], weights=[0.02, 0.05, 0.15, 0.38, 0.40])[0]
```

#### 策略3: 条件依赖
```python
# 根据前面问题的答案生成后续答案
if answers['q1'] == 1:  # 如果是男性
    answers['q13'] = random.choice(['数码家电', '运动户外', '汽车用品'])
else:  # 如果是女性
    answers['q13'] = random.choice(['美妆护肤', '服装鞋包', '母婴用品'])
```

#### 策略4: 逻辑一致性
```python
# 确保答案之间逻辑一致
if answers['q8'] == 1:  # 如果购物频率是"每天"
    # NPS推荐度应该较高
    answers['q11'] = random.randint(8, 10)
    # 满意度也应该较高
    answers['q10'] = random.randint(4, 5)
```

---

## 三、AI 适配新问卷的流程

### 3.1 问卷分析阶段

**步骤1: 获取问卷HTML**
```python
# 使用浏览器工具获取完整HTML
html_content = await page.content()
```

**步骤2: 识别所有题目**
- 查找所有 `<div class="field">` 或 `<div class="div_question">`
- 提取题目ID（通常在 `id` 或 `fid` 属性中）
- 记录题目类型（查看子元素结构）

**步骤3: 为每个题目确定题型**

| 题型判断依据 | 题型 |
|-------------|------|
| 包含 `<input type="radio">` + `.jqradio` | 单选题 |
| 包含 `<input type="checkbox">` + `.jqcheck` | 多选题 |
| 包含 `<select>` 元素 | 下拉选择题 |
| 包含 `<input type="text">` 单个 | 文本输入题 |
| 包含 `<textarea>` | 多行文本题 |
| 包含 `<table>` + 多个 `tr[fid]` + `a[dval]` | 矩阵评分题 |
| 包含 `<ul class="modlen5">` + `a.rate-off` | 评分题（1-5分）|
| 包含 `<ul class="modlen11">` + `a.rate-off` | NPS评分题（0-10分）|
| 包含 `<ul>` + 多个 `li[serial]` | 排序题 |

### 3.2 代码生成阶段

为每个题目生成填写代码，使用本文档第一部分的模板。

### 3.3 答案生成器生成阶段

为每个题目生成答案生成方法，根据题型选择合适的策略。

---

## 四、题型选择器快速查询表

| 题型 | 题号示例 | 选择器模板 | 注意事项 |
|------|---------|-----------|---------|
| 单选 | Q1, Q4, Q5, Q8 | `.label[for="qN_VALUE"]` | 点击label，不要点击input |
| 多选 | Q6, Q9 | `.label[for="qN_VALUE"]` | 使用click，不要用check |
| 下拉 | Q2 | `select[name="qN"]` | 直接select_option |
| 文本 | Q13 | `#qN` | 使用fill方法 |
| 只读文本 | Q3 | JavaScript设置value | 绕过readonly限制 |
| 多行文本 | Q14 | `textarea#qN` | 可以留空 |
| 矩阵评分 | Q7_0~Q7_5 | `tr[fid="qN_I"] a[dval="V"]` | 点击评分元素 |
| 评分题 | Q10 | `#divN a.rate-off[val="V"]` | val=实际分数 |
| NPS评分 | Q11 | `#divN a.rate-off[val="V+1"]` | val=实际分数+1 |
| 排序题 | Q12 | `li.ui-li-static[serial="V"]` | 依次点击所有选项 |

---

## 五、完整示例：生成新问卷的适配代码

假设有一个新问卷，包含以下题目：
- Q1: 年龄（单选，5个选项）
- Q2: 兴趣爱好（多选，8个选项）
- Q3: 满意度（评分，1-5分）
- Q4: 建议（多行文本）

### 5.1 生成填写代码

```python
async def _fill_by_type(self, page: Page, q_id: str, answer):
    """根据题型填写答案"""
    try:
        # Q1: 年龄（单选）
        if q_id == 'q1':
            await page.click(f'.label[for="q1_{answer}"]')

        # Q2: 兴趣爱好（多选）
        elif q_id == 'q2':
            if isinstance(answer, list):
                for option in answer:
                    await page.click(f'.label[for="q2_{option}"]')

        # Q3: 满意度（评分）
        elif q_id == 'q3':
            await page.click(f'#div3 a.rate-off[val="{answer}"]')

        # Q4: 建议（多行文本）
        elif q_id == 'q4':
            if answer:
                await page.fill('textarea#q4', answer)

    except Exception as e:
        print(f"填写问题 {q_id} 时出错: {e}")
```

### 5.2 生成答案生成器

```python
class NewQuestionnaireAnswerGenerator:
    """新问卷答案生成器"""

    def generate_answers(self, constraints: dict = None) -> dict:
        answers = {}

        if constraints:
            answers.update(constraints)

        # Q1: 年龄（单选）
        if 'q1' not in answers:
            answers['q1'] = random.choices(
                [1, 2, 3, 4, 5],  # 18以下, 18-25, 26-35, 36-50, 50以上
                weights=[0.05, 0.30, 0.35, 0.20, 0.10]
            )[0]

        # Q2: 兴趣爱好（多选）
        if 'q2' not in answers:
            answers['q2'] = random.sample(range(1, 9), k=random.randint(2, 4))

        # Q3: 满意度（评分）
        if 'q3' not in answers:
            answers['q3'] = random.choices(
                [1, 2, 3, 4, 5],
                weights=[0.02, 0.05, 0.15, 0.38, 0.40]
            )[0]

        # Q4: 建议（多行文本，80%概率填写）
        if 'q4' not in answers:
            if random.random() < 0.8:
                suggestions = [
                    '整体体验不错，希望继续保持。',
                    '服务质量很好，非常满意。',
                    '建议增加更多功能和选项。',
                ]
                answers['q4'] = random.choice(suggestions)
            else:
                answers['q4'] = ''

        return answers
```

---

## 六、常见问题与解决方案

### 6.1 选择器超时问题

**问题**: `Timeout 30000ms exceeded`

**原因**:
- 点击了隐藏的 `<input>` 元素
- 选择器不正确

**解决方案**:
- 单选/多选题必须点击 `.label[for="..."]` 元素
- 使用浏览器开发者工具验证选择器

### 6.2 排序题未完成

**问题**: 排序题只点击了部分选项

**原因**:
- 列表长度验证不正确
- 点击间隔过短

**解决方案**:
- 添加 `len(answer) == 选项数量` 验证
- 增加点击间隔到400ms

### 6.3 只读输入框无法填写

**问题**: `page.fill()` 对只读输入框无效

**解决方案**:
```python
await page.evaluate(f'document.getElementById("q3").value = "{answer}"')
```

### 6.4 NPS评分选择错误

**问题**: NPS评分选择了错误的分数

**原因**: `val` 属性比实际分数大1

**解决方案**:
```python
await page.click(f'#div11 a.rate-off[val="{answer + 1}"]')  # 注意 +1
```

---

## 七、版本历史

### v1.0 (2026-07-22)
- 初始版本
- 基于问卷星移动版（jQuery Mobile框架）
- 涵盖9种主要题型
- 包含完整的选择器模板和答案生成模式
- 提供AI适配新问卷的完整流程

---

## 八、参考文档

- `E:\learn\问卷星\选择器修复最终版.md` - 所有题型的最终选择器
- `E:\learn\问卷星\core\answer_generator.py` - 答案生成器实现
- `E:\learn\问卷星\core\submitter.py` - 表单填写实现
- `E:\learn\问卷星\测试结果.md` - 测试结果和验证

---

**文档结束**
