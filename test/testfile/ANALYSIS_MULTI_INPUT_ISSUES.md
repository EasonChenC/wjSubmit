# 多输入框问卷题目分析与修复方案

## 问题总结

通过MCP分析问卷 https://v.wjx.cn/vm/t3tsMH5.aspx 的HTML结构，发现以下5类问题：

### 1. Q1类：多个命名输入框（q1_1, q1_2, q1_3, q1_4）
**HTML结构：**
```html
<div class="field" id="div1" topic="1" type="9">
  调查地点: <input type="text" id="q1_1" name="q1_1" />市
  <input type="text" id="q1_2" name="q1_2" />县（区）
  <input type="text" id="q1_3" name="q1_3" />镇（乡）
  <input type="text" id="q1_4" name="q1_4" />村
</div>
```

**当前问题：**
- 规则引擎只识别出1个题目 `q1`
- 答案生成器只生成1个答案
- 填写器只尝试填写 `q1`，但实际有4个输入框

**修复方案：**
1. **规则引擎**：识别出这是多子输入框题目，拆分为 `q1_1`, `q1_2`, `q1_3`, `q1_4` 四个子题
2. **答案生成器**：为每个子输入框生成独立答案
3. **填写器**：使用 `getElementById(q1_1)` 等直接填写

---

### 2. Q3类：input无id/name属性（匿名输入框）
**HTML结构：**
```html
<div class="field" id="div3" topic="3" type="9">
  2.您的年龄:<input type="text" class="ui-input-text" />岁
</div>
```

**当前问题：**
- input元素**完全没有id和name属性**
- 无法通过 `getElementById()` 访问
- 当前所有填写策略都失败

**同类题目：**
- Q3: 年龄
- Q10: 家庭总人口数
- Q11: 劳动力人数
- Q12: 耕地面积
- Q13: 林地面积
- Q14: 距离

**修复方案：**
使用CSS选择器定位：
```javascript
// 方法1: 通过父容器查找第一个text input
selector = `#div${topic_num} input[type="text"]`

// 方法2: 使用XPath
selector = `//div[@id='div${topic_num}']//input[@type='text'][1]`
```

---

### 3. Q16类：多个命名子输入框（q16_1至q16_8）
**HTML结构：**
```html
<div class="field" id="div16" topic="16" type="9">
  15.请您估计2025年您家庭以下各类收入的大致金额（单位:元/年）:
  农业种植收入:<input type="text" id="q16_1" name="q16_1" />元;
  林业收入:<input type="text" id="q16_2" name="q16_2" />元;
  畜牧业收入:<input type="text" id="q16_3" name="q16_3" />元;
  本地务工/经商收入:<input type="text" id="q16_4" name="q16_4" />元;
  外出务工收入:<input type="text" id="q16_5" name="q16_5" />元;
  自然教育相关服务收入:<input type="text" id="q16_6" name="q16_6" />元;
  生态补偿/补贴收入:<input type="text" id="q16_7" name="q16_7" />元;
  其他收入:<input type="text" id="q16_8" name="q16_8" />元
</div>
```

**当前问题：**
- 与Q1类似，但有8个子输入框
- 需要拆分为8个子题

**修复方案：**
同Q1，拆分为独立子题

---

### 4. 多选题"其他"选项的动态文本框
**HTML结构：**
```html
<div class="ui-checkbox">
  <input type="checkbox" value="8" id="q9_8" name="q9" rel="tqq9_8" />
  <a class="jqcheck"></a>
  <div class="label" for="q9_8">⑧其他</div>
  <div class="ui-text" id="utq9_8">
    <input type="text" autocomplete="off" rel="q9_8" id="tqq9_8" required="true" class="OtherText" />
    <span class="req requireSpan">*</span>
  </div>
</div>
```

**当前问题：**
- 当checkbox `q9_8` 被选中时，需要填写文本框 `tqq9_8`
- 当前系统不处理"其他"选项的文本框

**识别方法：**
- checkbox有 `rel` 属性，值为文本框的id
- 文本框有class `OtherText`

**受影响的题目：**
- Q9 (q9_8 -> tqq9_8)
- Q19 (q19_7 -> tqq19_7)
- Q22 (q22_6 -> tqq22_6)
- Q23 (q23_7 -> tqq23_7)
- Q28 (q28_7 -> tqq28_7)
- Q29 (q29_7 -> tqq29_7)
- Q31 (q31_6 -> tqq31_6)
- Q32 (q32_7 -> tqq32_7)
- Q34 (q34_8 -> tqq34_8)
- Q35 (q35_8 -> tqq35_8)
- Q37 (q37_7 -> tqq37_7)
- Q38 (q38_6 -> tqq38_6)
- Q40 (q40_6 -> tqq40_6)
- Q43 (q43_7 -> tqq43_7)
- Q58 (q58_6 -> tqq58_6)
- Q62 (q62_7 -> tqq62_7)

**修复方案：**
1. **规则引擎**：检测checkbox的 `rel` 属性，创建关联的文本输入题
2. **答案生成器**：如果选择了"其他"选项，为其文本框生成答案
3. **填写器**：选择checkbox后，填写对应的文本框

---

## 实现计划

### 阶段1：修改规则引擎（rule_based_analyzer.py）

#### 1.1 识别多输入框文本题
```python
def _extract_text_sub_inputs(self, div: Tag, question_id: str) -> List[Question]:
    """识别并拆分多输入框文本题"""
    inputs = div.find_all('input', attrs={'type': 'text'})

    # 情况1: 所有input都有id（如 q1_1, q1_2...）
    named_inputs = [inp for inp in inputs if inp.get('id')]
    if len(named_inputs) >= 2:
        return self._create_named_sub_questions(named_inputs, question_id)

    # 情况2: input没有id（匿名）
    if len(inputs) == 1 and not inputs[0].get('id'):
        return [self._create_anonymous_question(div, question_id)]

    # 情况3: 只有1个有id的input
    return []
```

#### 1.2 识别多选题"其他"选项
```python
def _extract_checkbox_other_text(self, div: Tag, question: Question) -> Optional[Question]:
    """检测多选题的"其他"选项文本框"""
    # 查找所有checkbox
    checkboxes = div.find_all('input', attrs={'type': 'checkbox'})

    for checkbox in checkboxes:
        rel_attr = checkbox.get('rel')
        if rel_attr and rel_attr.startswith('tqq'):
            # 找到对应的文本框
            text_input = div.find('input', attrs={'id': rel_attr})
            if text_input:
                # 创建关联的文本输入题
                return self._create_other_text_question(checkbox, text_input)

    return None
```

### 阶段2：修改答案生成器（dynamic_answer_generator.py）

```python
def generate_answers(self) -> Dict[str, Any]:
    """生成答案，支持子输入框和其他选项"""
    answers = {}

    for question in self.schema.questions:
        answer = self._generate_answer(question)
        answers[question.id] = answer

        # 如果是多选题且选择了"其他"选项
        if question.type == QuestionType.CHECKBOX and isinstance(answer, list):
            for option_id in answer:
                # 检查是否有关联的"其他"文本框
                other_text_id = self._get_other_text_id(question, option_id)
                if other_text_id:
                    answers[other_text_id] = self._generate_other_text()

    return answers
```

### 阶段3：修改填写器（dynamic_submitter.py）

#### 3.1 填写匿名文本框
```python
async def _fill_anonymous_text(self, page: Page, question: Question, answer: str):
    """填写没有id/name的文本框"""
    # 提取题号
    topic_num = question.metadata.get('topic_num')

    # 策略1: 通过父容器查找
    selector = f'#div{topic_num} input[type="text"]'
    try:
        await page.fill(selector, answer, timeout=3000)
        return
    except:
        pass

    # 策略2: 使用evaluate直接操作
    result = await page.evaluate(f"""
        (function() {{
            var div = document.getElementById('div{topic_num}');
            if (div) {{
                var inputs = div.querySelectorAll('input[type="text"]');
                if (inputs.length > 0) {{
                    inputs[0].value = '{answer}';
                    return true;
                }}
            }}
            return false;
        }})();
    """)

    if not result:
        print(f"  [WARN] 无法填写匿名文本框: div{topic_num}")
```

#### 3.2 填写"其他"选项文本框
```python
async def _fill_checkbox(self, page: Page, question: Question, answer: List[int]):
    """填写多选题，包括其他选项的文本框"""
    for option_id in answer:
        # 点击checkbox
        await self._click_checkbox_option(page, question.id, option_id)

        # 检查是否是"其他"选项
        other_text_id = question.metadata.get(f'other_text_{option_id}')
        if other_text_id:
            # 需要填写关联的文本框
            other_answer = self.answers.get(other_text_id)
            if other_answer:
                await self._fill_other_text_input(page, other_text_id, other_answer)
```

---

## 测试计划

1. 测试Q1（4个命名子输入框）
2. 测试Q3（匿名输入框）
3. 测试Q16（8个命名子输入框）
4. 测试Q9（多选题+其他选项文本框）
5. 完整端到端测试

---

## 预期结果

所有文本输入框都能正确填写，多选题的"其他"选项也能正确填写关联文本框。
