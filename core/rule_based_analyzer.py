# rule_based_analyzer.py
"""
规则引擎分析器

基于HTML解析和模式匹配识别问卷题型，生成QuestionnaireSchema。
使用skill.md中定义的识别规则。
"""

import re
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag
from urllib.parse import urlparse

from .schema import (
    QuestionnaireSchema,
    Question,
    QuestionType,
    SelectorConfig,
    AnswerStrategy,
    SELECTOR_TEMPLATES,
    STRATEGY_TEMPLATES,
)


class RuleBasedAnalyzer:
    """规则引擎分析器

    基于HTML结构和CSS选择器模式识别问卷题型。
    """

    def __init__(self):
        """初始化分析器"""
        self.platform = "wjx"  # 默认问卷星平台

    def analyze(self, html: str, url: str) -> QuestionnaireSchema:
        """分析HTML并生成问卷Schema

        Args:
            html: 问卷HTML内容
            url: 问卷URL

        Returns:
            QuestionnaireSchema对象
        """
        soup = BeautifulSoup(html, 'html.parser')

        # 提取活动ID
        activity_id = self._extract_activity_id(url)

        # 识别平台
        platform = self._detect_platform(soup, url)

        # 提取问卷标题与介绍（问卷背景信息，影响量表题正反向判断）
        title = self._extract_title(soup)
        description = self._extract_description(soup)

        # 提取所有题目
        questions = self._extract_questions(soup)

        # 创建Schema
        schema = QuestionnaireSchema(
            url=url,
            activity_id=activity_id,
            platform=platform,
            questions=questions,
            metadata={
                'total_questions': len(questions),
                'identified_types': self._count_types(questions),
                'title': title,
                'description': description,
            }
        )

        return schema

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取问卷标题

        问卷星将标题渲染在 <h1 class="htitle" id="htitle">，
        取不到时回退到 <title> 标签。

        Args:
            soup: BeautifulSoup对象

        Returns:
            问卷标题文本，未找到返回空字符串
        """
        h1 = soup.find('h1', class_='htitle') or soup.find(id='htitle')
        if h1:
            return h1.get_text(strip=True)

        if soup.title:
            return soup.title.get_text(strip=True)

        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """提取问卷介绍/说明文字

        问卷星将介绍渲染在 <div id="divDesc"><span class="description">...</span></div>，
        内容可能是多个<p>段落，也可能是不带标签的纯文本。

        Args:
            soup: BeautifulSoup对象

        Returns:
            问卷介绍文本，未找到返回空字符串
        """
        desc_span = soup.find('span', class_='description')
        if desc_span:
            return desc_span.get_text(separator='\n', strip=True)

        return ""

    def _extract_activity_id(self, url: str) -> str:
        """从URL中提取活动ID

        例如: https://v.wjx.cn/vm/rqKTYry.aspx -> rqKTYry
        """
        match = re.search(r'/([a-zA-Z0-9]+)\.aspx', url)
        if match:
            return match.group(1)

        # 备选方案：使用URL路径的最后一部分
        path = urlparse(url).path
        return path.strip('/').split('/')[-1].replace('.aspx', '')

    def _detect_platform(self, soup: BeautifulSoup, url: str) -> str:
        """检测问卷平台

        Args:
            soup: BeautifulSoup对象
            url: 问卷URL

        Returns:
            平台标识: "wjx", "wjcn", "tencent", etc.
        """
        # 基于URL判断
        if 'wjx.cn' in url or 'wenjuan.com' in url:
            return 'wjx'
        elif 'wjuan.cn' in url:
            return 'wjcn'
        elif 'wj.qq.com' in url:
            return 'tencent'

        # 基于HTML特征判断
        if soup.find('meta', attrs={'name': 'author', 'content': re.compile('问卷星', re.I)}):
            return 'wjx'

        return 'unknown'

    def _extract_questions(self, soup: BeautifulSoup) -> List[Question]:
        """提取所有题目

        Args:
            soup: BeautifulSoup对象

        Returns:
            Question对象列表
        """
        questions = []
        seen_ids = set()  # 用于去重

        # 查找所有题目容器
        # 问卷星使用 <div class="field"> 或 <div class="div_question">
        question_divs = soup.find_all('div', class_=re.compile(r'field|div_question'))

        for div in question_divs:
            # 提取题目ID
            question_id = self._extract_question_id(div)
            if not question_id:
                continue

            # 识别题型
            question_type = self._identify_question_type(div)

            # 如果是矩阵题，需要特殊处理（拆分为多个子题）
            if question_type == QuestionType.MATRIX:
                matrix_questions = self._extract_matrix_questions(div, question_id)
                questions.extend(matrix_questions)
                # 矩阵题的子题ID已经在函数内处理，不需要额外去重

            # 如果是多输入框文本题，需要拆分为子题
            elif question_type == QuestionType.TEXT:
                text_questions = self._extract_text_sub_questions(div, question_id)
                if text_questions:
                    # 成功拆分为多个子题，添加到结果并标记为已见
                    for tq in text_questions:
                        if tq.id not in seen_ids:
                            questions.append(tq)
                            seen_ids.add(tq.id)
                else:
                    # 单个文本题，按原流程处理
                    if question_id in seen_ids:
                        continue
                    seen_ids.add(question_id)

                    label = self._extract_question_label(div)
                    options = self._extract_options(div, question_type)
                    selector = self._generate_selector(question_id, question_type)
                    strategy = self._generate_strategy(question_type, options)
                    required = self._is_required(div)
                    metadata = self._extract_metadata(div, question_type)

                    question = Question(
                        id=question_id,
                        type=question_type,
                        label=label,
                        options=options,
                        selector=selector,
                        strategy=strategy,
                        required=required,
                        metadata=metadata,
                    )
                    questions.append(question)
            else:
                # 去重：如果这个ID已经见过，跳过
                if question_id in seen_ids:
                    continue
                seen_ids.add(question_id)

                # 提取题目标签
                label = self._extract_question_label(div)

                # 提取选项
                options = self._extract_options(div, question_type)

                # 生成选择器配置
                selector = self._generate_selector(question_id, question_type)

                # 生成答案策略
                strategy = self._generate_strategy(question_type, options, div=div)

                # 判断是否必填
                required = self._is_required(div)

                # 提取元数据
                metadata = self._extract_metadata(div, question_type)

                question = Question(
                    id=question_id,
                    type=question_type,
                    label=label,
                    options=options,
                    selector=selector,
                    strategy=strategy,
                    required=required,
                    metadata=metadata,
                )

                questions.append(question)

                # 如果是多选题，检查是否有"其他"选项的文本框
                if question_type == QuestionType.CHECKBOX:
                    other_text_question = self._extract_checkbox_other_text(div, question)
                    if other_text_question and other_text_question.id not in seen_ids:
                        questions.append(other_text_question)
                        seen_ids.add(other_text_question.id)

        return questions

    def _extract_question_id(self, div: Tag) -> Optional[str]:
        """提取题目ID

        Args:
            div: 题目div元素

        Returns:
            题目ID，如 "q1", "q2"，失败返回None
        """
        # 方法1: 查找id属性（如 id="q1" 或 id="div1"）
        div_id = div.get('id')
        if div_id:
            # 情况1: id直接是qN格式
            if re.match(r'q\d+$', div_id):
                return div_id
            # 情况2: id是divN格式，转换为qN
            match = re.match(r'div(\d+)$', div_id)
            if match:
                return f'q{match.group(1)}'

        # 方法2: 查找field属性
        field_id = div.get('field')
        if field_id and re.match(r'q\d+', field_id):
            return field_id

        # 方法3: 使用topic属性（如 topic="3"）
        topic = div.get('topic')
        if topic and topic.isdigit():
            return f'q{topic}'

        # 方法4: 查找内部input/select的name或id
        input_elem = div.find(['input', 'select', 'textarea'])
        if input_elem:
            name = input_elem.get('name') or input_elem.get('id')
            if name and re.match(r'q\d+', name):
                return re.match(r'q\d+', name).group(0)

        return None

    def _identify_question_type(self, div: Tag) -> QuestionType:
        """识别题型

        基于skill.md中的识别规则。

        Args:
            div: 题目div元素

        Returns:
            QuestionType枚举值
        """
        # 1. 单选题: <input type="radio"> + .jqradio
        if div.find('input', attrs={'type': 'radio'}) and div.find(class_='jqradio'):
            return QuestionType.RADIO

        # 2. 多选题: <input type="checkbox"> + .jqcheck
        if div.find('input', attrs={'type': 'checkbox'}) and div.find(class_='jqcheck'):
            return QuestionType.CHECKBOX

        # 3. 下拉选择题: <select>
        if div.find('select'):
            return QuestionType.SELECT

        # 4. NPS评分题: <ul class="modlen11"> (0-10分)
        ul_nps = div.find('ul', class_=re.compile(r'modlen11'))
        if ul_nps and ul_nps.find('a', class_='rate-off'):
            return QuestionType.NPS

        # 5. 评分题: <ul class="modlen5"> (1-5分)
        ul_rating = div.find('ul', class_=re.compile(r'modlen5'))
        if ul_rating and ul_rating.find('a', class_='rate-off'):
            return QuestionType.RATING

        # 6. 矩阵评分题: <table> + tr[fid] + a[dval]
        table = div.find('table')
        if table:
            tr_with_fid = table.find('tr', attrs={'fid': True})
            if tr_with_fid and tr_with_fid.find('a', attrs={'dval': True}):
                return QuestionType.MATRIX

        # 7. 排序题: <ul> + li[serial]
        ul_sort = div.find('ul')
        if ul_sort and ul_sort.find('li', attrs={'serial': True}):
            return QuestionType.SORT

        # 7.5 权重题: <table> + input[class="ui-slider-input"] + total="100"
        if div.get('total') == '100' or div.get('type') == '12':
            table = div.find('table')
            if table:
                slider_inputs = table.find_all('input', class_='ui-slider-input')
                if slider_inputs:
                    return QuestionType.WEIGHT

        # 8. 多行文本题: <textarea>
        if div.find('textarea'):
            return QuestionType.TEXTAREA

        # 9. 文本输入题: <input type="text"> 或 contenteditable span
        if div.find('input', attrs={'type': 'text'}):
            return QuestionType.TEXT

        # 10. Contenteditable文本题: type="9" + gapfill="1" + span[contenteditable]
        if (div.get('type') == '9' and div.get('gapfill') == '1' and
            div.find('span', class_='textCont', attrs={'contenteditable': True})):
            return QuestionType.TEXT

        # 未识别
        return QuestionType.UNKNOWN

    def _extract_matrix_questions(self, div: Tag, base_id: str) -> List[Question]:
        """提取矩阵题的所有子题

        矩阵题需要拆分为多个独立的Question对象，每行一个。

        Args:
            div: 矩阵题div元素
            base_id: 基础ID，如 "q7"

        Returns:
            Question对象列表，如 [q7_0, q7_1, q7_2, ...]
        """
        questions = []

        # 查找所有带fid属性的tr元素
        table = div.find('table')
        if not table:
            return questions

        # 提取表头标签（如"很不满意"/"不满意"/.../"很满意"），
        # 与各评分列的dval顺序一一对应（表头第一个th为空，对应行标题列，需跳过）
        header_row = table.find('tr', class_='trlabel')
        header_labels = []
        if header_row:
            header_labels = [th.get_text(strip=True) for th in header_row.find_all('th')][1:]

        rows = table.find_all('tr', attrs={'fid': True})

        for row in rows:
            row_id = row.get('fid')  # 如 "q7_0", "q7_1"
            if not row_id:
                continue

            # 提取行标签（第一个td的文本）
            label_td = row.find('td')
            label = label_td.get_text(strip=True) if label_td else ""

            # 提取评分选项（从a[dval]中获取），并用表头文本作为label
            rating_links = row.find_all('a', attrs={'dval': True})
            options = []
            for idx, link in enumerate(rating_links):
                dval = link.get('dval')
                try:
                    value = int(dval)
                except (TypeError, ValueError):
                    value = dval
                opt_label = header_labels[idx] if idx < len(header_labels) else str(value)
                options.append({"value": value, "label": opt_label})

            # 生成选择器
            selector = SelectorConfig(
                template="a[dval='{value}']",
                container=f"tr[fid='{row_id}']",
                special_handling=None
            )

            # 生成策略（矩阵评分倾向高分）
            strategy = AnswerStrategy(
                type="random_int",
                params={"min": 3, "max": 5}
            )

            question = Question(
                id=row_id,
                type=QuestionType.MATRIX,
                label=label,
                options=options,
                selector=selector,
                strategy=strategy,
                required=True,
                metadata={'base_id': base_id}
            )

            questions.append(question)

        return questions

    def _extract_text_sub_questions(self, div: Tag, base_id: str) -> List[Question]:
        """提取多输入框文本题的所有子题

        处理4种情况：
        1. 多个有id的input (如 q1_1, q1_2, q1_3, q1_4) - 优先级最高
        2. 单个无id的input (如年龄题)
        3. Contenteditable span (如年龄题的新版本)
        4. 普通单输入框 (返回空列表，由调用方按原流程处理)

        Args:
            div: 文本题div元素
            base_id: 基础ID，如 "q1"

        Returns:
            Question对象列表
        """
        questions = []

        # 查找所有text类型的input
        all_inputs = div.find_all('input', attrs={'type': 'text'})

        # 分类：可见的input 和 有id的隐藏input
        visible_inputs = []
        hidden_inputs_with_id = []

        for inp in all_inputs:
            style = inp.get('style', '')
            is_hidden = 'display:none' in style or 'display: none' in style or 'visibility:hidden' in style

            if is_hidden:
                # 隐藏但有id的input（如q1_1），可能配对contenteditable
                if inp.get('id'):
                    hidden_inputs_with_id.append(inp)
            else:
                visible_inputs.append(inp)

        # 优先级1: 多个有id的隐藏input + contenteditable (如Q1的q1_1-q1_4)
        # 这种情况下，input虽然隐藏，但用户通过contenteditable填写
        if len(hidden_inputs_with_id) >= 2:
            # 检查是否每个input后面都有contenteditable span
            has_contenteditable = div.find('span', class_='textCont', attrs={'contenteditable': True})

            if has_contenteditable:
                # 这是contenteditable多输入框题目
                for inp in hidden_inputs_with_id:
                    input_id = inp.get('id')
                    if not input_id or not input_id.startswith(base_id):
                        continue

                    # 提取label
                    label = self._extract_sub_input_label(inp)

                    # 生成选择器 - 注意：选择contenteditable span，而不是input！
                    # 通过input的id来定位对应的contenteditable span
                    selector = SelectorConfig(
                        template=f"input[id='{input_id}'] ~ label span.textCont[contenteditable='true']",
                        special_handling="contenteditable_with_id"
                    )

                    # 生成策略
                    strategy = AnswerStrategy(
                        type="random_text",
                        params={"length": 5}
                    )

                    question = Question(
                        id=input_id,
                        type=QuestionType.TEXT,
                        label=label,
                        options=[],
                        selector=selector,
                        strategy=strategy,
                        required=True,
                        metadata={'base_id': base_id, 'sub_input': True, 'contenteditable_input': True}
                    )

                    questions.append(question)

                return questions

        inputs = visible_inputs  # 后续只处理可见的input

        # 优先级1: 多个有id的input (如 q1_1, q1_2, q1_3, q1_4)
        if inputs:
            named_inputs = [inp for inp in inputs if inp.get('id') and inp.get('id').startswith(base_id)]
            if len(named_inputs) >= 2:
                # 这是多输入框题目
                for inp in named_inputs:
                    input_id = inp.get('id')
                    if not input_id:
                        continue

                    # 提取label（从前面的文本）
                    label = self._extract_sub_input_label(inp)

                    # 生成选择器（直接使用input的id）
                    selector = SelectorConfig(
                        template=f"#{input_id}",
                        special_handling=None
                    )

                    # 生成策略（随机城市/地名/数字）
                    strategy = AnswerStrategy(
                        type="random_text",
                        params={"length": 5}
                    )

                    question = Question(
                        id=input_id,
                        type=QuestionType.TEXT,
                        label=label,
                        options=[],
                        selector=selector,
                        strategy=strategy,
                        required=True,
                        metadata={'base_id': base_id, 'sub_input': True}
                    )

                    questions.append(question)

                return questions

        # 优先级2: 单个无id的input (匿名输入框)
        if inputs and len(inputs) == 1 and not inputs[0].get('id'):
            # 获取topic属性
            topic_num = div.get('topic')
            if not topic_num:
                return []

            # 提取题目标签
            label = self._extract_question_label(div)

            # 生成选择器（使用父容器定位）
            selector = SelectorConfig(
                template=f"#div{topic_num} input[type='text']",
                special_handling="anonymous_input"
            )

            # 生成策略（随机数字，因为多数是数量/金额/距离）
            strategy = AnswerStrategy(
                type="random_int",
                params={"min": 1, "max": 100}
            )

            question = Question(
                id=base_id,
                type=QuestionType.TEXT,
                label=label,
                options=[],
                selector=selector,
                strategy=strategy,
                required=True,
                metadata={'topic_num': topic_num, 'anonymous': True}
            )

            questions.append(question)
            return questions

        # 优先级3: Contenteditable span (只有在没有input或input不符合条件时才检查)
        contenteditable_span = div.find('span', class_='textCont', attrs={'contenteditable': True})
        if contenteditable_span and div.get('type') == '9' and div.get('gapfill') == '1':
            # 这是contenteditable文本题
            topic_num = div.get('topic')
            if not topic_num:
                return []

            # 提取题目标签
            label = self._extract_question_label(div)

            # 生成选择器（使用contenteditable span）
            selector = SelectorConfig(
                template=f"#div{topic_num} span.textCont[contenteditable='true']",
                special_handling="contenteditable"
            )

            # 生成策略（随机数字，因为多数是数量/金额/距离）
            strategy = AnswerStrategy(
                type="random_int",
                params={"min": 1, "max": 100}
            )

            question = Question(
                id=base_id,
                type=QuestionType.TEXT,
                label=label,
                options=[],
                selector=selector,
                strategy=strategy,
                required=True,
                metadata={'topic_num': topic_num, 'contenteditable': True}
            )

            questions.append(question)
            return questions

        # 优先级4: 普通单输入框，返回空列表，由调用方处理
        return []

    def _extract_sub_input_label(self, input_elem: Tag) -> str:
        """提取子输入框的标签

        尝试找到input前面的文本作为标签

        Args:
            input_elem: input元素

        Returns:
            标签文本
        """
        # 获取input前面的文本
        prev_text = ""
        for sibling in input_elem.previous_siblings:
            if isinstance(sibling, str):
                text = sibling.strip()
                if text and text not in ['*', ':', '：', '，', '。', ';', '；']:
                    prev_text = text + prev_text
            elif sibling.name in ['label', 'span']:
                text = sibling.get_text(strip=True)
                if text:
                    prev_text = text + prev_text

        if prev_text:
            return prev_text[-20:]  # 返回最后20个字符

        # 如果没找到，返回input的id
        return input_elem.get('id', '未命名')

    def _extract_checkbox_other_text(self, div: Tag, checkbox_question: Question) -> Optional[Question]:
        """提取多选题"其他"选项的文本框

        当多选题有"其他"选项时，选择该选项后会出现一个文本输入框。
        HTML结构：
        <input type="checkbox" id="q9_8" rel="tqq9_8" />
        <div class="ui-text" id="utq9_8">
            <input type="text" id="tqq9_8" rel="q9_8" class="OtherText" />
        </div>

        Args:
            div: 多选题div元素
            checkbox_question: 已创建的多选题对象

        Returns:
            "其他"选项的文本输入题，如果没有则返回None
        """
        # 查找所有checkbox
        checkboxes = div.find_all('input', attrs={'type': 'checkbox'})

        for checkbox in checkboxes:
            rel_attr = checkbox.get('rel')
            # rel属性指向关联的文本框id（如 "tqq9_8"）
            if rel_attr and rel_attr.startswith('tqq'):
                checkbox_id = checkbox.get('id')  # 如 "q9_8"
                if not checkbox_id:
                    continue

                # 查找对应的文本框
                text_input = div.find('input', attrs={'id': rel_attr, 'class': 'OtherText'})
                if not text_input:
                    continue

                # 提取选项编号（如 q9_8 -> 8）
                match = re.search(r'_(\d+)$', checkbox_id)
                if not match:
                    continue

                option_num = int(match.group(1))

                # 创建文本输入题
                selector = SelectorConfig(
                    template=f"#{rel_attr}",
                    special_handling="other_option_text"
                )

                strategy = AnswerStrategy(
                    type="random_text",
                    params={"length": 10}
                )

                # 提取label（通常是"其他"后面的提示）
                label = f"{checkbox_question.label} - 其他选项说明"

                question = Question(
                    id=rel_attr,
                    type=QuestionType.TEXT,
                    label=label,
                    options=[],
                    selector=selector,
                    strategy=strategy,
                    required=True,
                    metadata={
                        'parent_question': checkbox_question.id,
                        'parent_option': option_num,
                        'other_option_text': True
                    }
                )

                # 在主问题的metadata中记录关联关系
                if not checkbox_question.metadata:
                    checkbox_question.metadata = {}
                checkbox_question.metadata[f'other_text_{option_num}'] = rel_attr

                return question

        return None

    def _extract_question_label(self, div: Tag) -> str:
        """提取题目文本

        Args:
            div: 题目div元素

        Returns:
            题目文本
        """
        # 方法1: 查找 <div class="field-label">
        label_div = div.find('div', class_=re.compile(r'field-label|question-title'))
        if label_div:
            text = label_div.get_text(strip=True)
            # 移除题号（如 "1. " 或 "Q1："）
            text = re.sub(r'^\d+[.、:：]\s*', '', text)
            text = re.sub(r'^Q\d+[.、:：]\s*', '', text, flags=re.I)
            return text

        # 方法2: 查找第一个非隐藏的文本
        for elem in div.find_all(['div', 'span', 'label']):
            if elem.get('style') and 'display:none' in elem.get('style'):
                continue
            text = elem.get_text(strip=True)
            if len(text) > 5:  # 至少5个字符
                text = re.sub(r'^\d+[.、:：]\s*', '', text)
                return text

        return "未识别题目"

    def _extract_options(self, div: Tag, question_type: QuestionType) -> List[Any]:
        """提取选项列表

        Args:
            div: 题目div元素
            question_type: 题型

        Returns:
            选项列表，格式根据题型不同
        """
        if question_type == QuestionType.RADIO:
            return self._extract_radio_options(div)
        elif question_type == QuestionType.CHECKBOX:
            return self._extract_checkbox_options(div)
        elif question_type == QuestionType.SELECT:
            return self._extract_select_options(div)
        elif question_type == QuestionType.RATING:
            return self._extract_rating_options(div, max_val=5)
        elif question_type == QuestionType.NPS:
            return self._extract_nps_options(div)
        elif question_type == QuestionType.SORT:
            return self._extract_sort_options(div)
        elif question_type == QuestionType.WEIGHT:
            return self._extract_weight_options(div)
        elif question_type in [QuestionType.TEXT, QuestionType.TEXTAREA]:
            return []  # 文本题没有选项
        else:
            return []

    def _extract_radio_options(self, div: Tag) -> List[Dict[str, Any]]:
        """提取单选题选项

        Returns:
            选项列表，如 [{"value": 1, "label": "选项1"}, ...]
        """
        options = {}
        radio_inputs = div.find_all('input', attrs={'type': 'radio'})

        for radio in radio_inputs:
            radio_id = radio.get('id')  # 如 "q1_1", "q1_2"
            if radio_id:
                match = re.search(r'_(\d+)$', radio_id)
                if match:
                    value = int(match.group(1))
                    label = ""

                    # 方法1: 查找 <div class="label" for="...">
                    label_elem = div.find('div', attrs={'class': 'label', 'for': radio_id})
                    if label_elem:
                        label = label_elem.get_text(strip=True)

                    # 方法2: 查找 <label for="...">（备选）
                    if not label:
                        label_elem = div.find('label', attrs={'for': radio_id})
                        if label_elem:
                            label = label_elem.get_text(strip=True)

                    # 方法3: 从radio的下一个兄弟查找（可能有其他结构）
                    if not label:
                        next_div = radio.find_next('div', class_='label')
                        if next_div:
                            label = next_div.get_text(strip=True)

                    options[value] = {"value": value, "label": label}

        # 按value排序返回
        return sorted(options.values(), key=lambda x: x['value'])

    def _extract_checkbox_options(self, div: Tag) -> List[Dict[str, Any]]:
        """提取多选题选项

        Returns:
            选项列表，如 [{"value": 1, "label": "选项1"}, ...]
        """
        options = {}
        checkbox_inputs = div.find_all('input', attrs={'type': 'checkbox'})

        for checkbox in checkbox_inputs:
            checkbox_id = checkbox.get('id')  # 如 "q6_1", "q6_2"
            if checkbox_id:
                match = re.search(r'_(\d+)$', checkbox_id)
                if match:
                    value = int(match.group(1))
                    label = ""

                    # 方法1: 查找 <div class="label" for="...">
                    label_elem = div.find('div', attrs={'class': 'label', 'for': checkbox_id})
                    if label_elem:
                        label = label_elem.get_text(strip=True)

                    # 方法2: 查找 <label for="...">（备选）
                    if not label:
                        label_elem = div.find('label', attrs={'for': checkbox_id})
                        if label_elem:
                            label = label_elem.get_text(strip=True)

                    # 方法3: 从checkbox的下一个兄弟查找
                    if not label:
                        next_div = checkbox.find_next('div', class_='label')
                        if next_div:
                            label = next_div.get_text(strip=True)

                    options[value] = {"value": value, "label": label}

        # 按value排序返回
        return sorted(options.values(), key=lambda x: x['value'])

    def _extract_select_options(self, div: Tag) -> List[Dict[str, Any]]:
        """提取下拉选择题选项

        Returns:
            选项列表，如 [{"value": 1, "label": "选项1"}, ...]
        """
        options = {}
        select_elem = div.find('select')

        if select_elem:
            option_elems = select_elem.find_all('option')
            for opt in option_elems:
                value = opt.get('value')
                # 跳过占位符（value="-2"或空）
                if value and value != '-2':
                    try:
                        value_int = int(value)
                        label = opt.get_text(strip=True) or ""
                        options[value_int] = {"value": value_int, "label": label}
                    except ValueError:
                        continue

        # 按value排序返回
        return sorted(options.values(), key=lambda x: x['value'])

    def _extract_rating_options(self, div: Tag, max_val: int = 5) -> List[Dict[str, Any]]:
        """提取评分题选项

        评分题的每个选项<a class="rate-off" val="1" title="很不同意">中，
        title属性即为选项的真实文本内容。

        Args:
            div: 题目div元素
            max_val: 最大评分值

        Returns:
            选项列表，如 [{"value": 1, "label": "很不同意"}, ...]
        """
        options = {}
        rating_links = div.find_all('a', class_='rate-off')

        for link in rating_links:
            val = link.get('val')
            if not val:
                continue
            try:
                value = int(val)
            except ValueError:
                continue

            label = link.get('title') or link.get_text(strip=True) or str(value)
            options[value] = {"value": value, "label": label}

        if options:
            return sorted(options.values(), key=lambda x: x['value'])

        # 默认返回1-max_val（无标签，兜底）
        return [{"value": v, "label": str(v)} for v in range(1, max_val + 1)]

    def _extract_nps_options(self, div: Tag) -> List[Dict[str, Any]]:
        """提取NPS推荐度选项（0-10分）

        HTML中<a val="1">对应分数0（val = 分数 + 1，与_fill_nps的+1偏移一致），
        title/文本内容为该分数对应的标签（如"不可能"/"极有可能"）。

        Returns:
            选项列表，如 [{"value": 0, "label": "不可能"}, ..., {"value": 10, "label": "极有可能"}]
        """
        options = {}
        rating_links = div.find_all('a', class_='rate-off')

        for link in rating_links:
            val = link.get('val')
            if not val:
                continue
            try:
                score = int(val) - 1  # val比实际分数大1
            except ValueError:
                continue

            label = link.get('title') or link.get_text(strip=True) or str(score)
            options[score] = {"value": score, "label": label}

        if options:
            return sorted(options.values(), key=lambda x: x['value'])

        # 默认返回0-10（无标签，兜底）
        return [{"value": v, "label": str(v)} for v in range(11)]

    def _extract_sort_options(self, div: Tag) -> List[int]:
        """提取排序题选项

        Returns:
            serial值列表，如 [1, 2, 3, 4, 5, 6]
        """
        options = []
        li_elems = div.find_all('li', attrs={'serial': True})

        for li in li_elems:
            serial = li.get('serial')
            if serial:
                try:
                    options.append(int(serial))
                except ValueError:
                    continue

        return sorted(set(options))

    def _generate_selector(self, question_id: str, question_type: QuestionType) -> SelectorConfig:
        """生成选择器配置

        Args:
            question_id: 题目ID
            question_type: 题型

        Returns:
            SelectorConfig对象
        """
        # 使用预定义的模板
        if question_type in SELECTOR_TEMPLATES:
            template = SELECTOR_TEMPLATES[question_type]
            return SelectorConfig(
                template=template.template,
                container=template.container,
                special_handling=template.special_handling
            )

        # 未知题型，返回默认选择器
        return SelectorConfig(
            template=f"#{question_id}",
            special_handling=None
        )

    def _generate_strategy(self, question_type: QuestionType, options: List[Any],
                            div: Optional[Tag] = None) -> AnswerStrategy:
        """生成答案策略

        Args:
            question_type: 题型
            options: 选项列表
            div: 题目div元素（用于读取多选题的 minvalue/maxvalue 限制）

        Returns:
            AnswerStrategy对象
        """
        # 使用预定义的策略模板
        if question_type in STRATEGY_TEMPLATES:
            template = STRATEGY_TEMPLATES[question_type]
            strategy = AnswerStrategy(
                type=template.type,
                params=template.params.copy()
            )

            # 根据实际选项数量调整参数
            if question_type == QuestionType.RADIO and not strategy.params.get('weights'):
                # 单选题：均等权重
                num_options = len(options)
                strategy.params['weights'] = [1.0 / num_options] * num_options

            elif question_type == QuestionType.SELECT and not strategy.params.get('weights'):
                # 下拉题：均等权重
                num_options = len(options)
                strategy.params['weights'] = [1.0 / num_options] * num_options

            elif question_type == QuestionType.CHECKBOX:
                # 多选题：默认抽样范围先按选项数量给出宽松上下限
                num_options = len(options)
                min_choices = min(2, num_options)
                max_choices = min(4, num_options)

                # 问卷星在题目容器上通过 minvalue/maxvalue 属性硬性限制
                # 最少/最多可选数量（如 minvalue="1" maxvalue="3"），必须遵守，
                # 否则提交时页面会报"最多选X项"导致流程卡住
                if div is not None:
                    raw_min = div.get('minvalue')
                    raw_max = div.get('maxvalue')

                    if raw_min is not None:
                        try:
                            min_choices = max(1, min(int(raw_min), num_options))
                        except ValueError:
                            pass

                    if raw_max is not None:
                        try:
                            max_choices = max(min_choices, min(int(raw_max), num_options))
                        except ValueError:
                            pass

                strategy.params['min'] = min_choices
                strategy.params['max'] = max_choices

            return strategy

        # 默认策略
        return AnswerStrategy(type="random_int", params={"min": 1, "max": len(options)})

    def _is_required(self, div: Tag) -> bool:
        """判断题目是否必填

        Args:
            div: 题目div元素

        Returns:
            True表示必填，False表示可选
        """
        # 查找必填标记（红色星号、"*"、class="required"等）
        if div.find('span', class_=re.compile(r'required|must')):
            return True

        if div.find('span', style=re.compile(r'color:\s*red')):
            text = div.get_text()
            if '*' in text or '必填' in text:
                return True

        # 默认为必填
        return True

    def _extract_metadata(self, div: Tag, question_type: QuestionType) -> Dict[str, Any]:
        """提取题目的额外元数据

        Args:
            div: 题目div元素
            question_type: 题型

        Returns:
            元数据字典
        """
        metadata = {}

        # 多选题的"其他"选项
        if question_type == QuestionType.CHECKBOX:
            # 查找"其他"文本框（id格式: tqq{题号}_{选项编号}）
            other_input = div.find('input', attrs={'id': re.compile(r'tqq\d+_\d+')})
            if other_input:
                metadata['other_text_id'] = other_input.get('id')

                # 通过 rel 属性找到对应的"其他"checkbox本身，记录其选项value，
                # 供答案生成时默认排除该选项（不勾选"其他"，避免必须额外填写说明文本）
                rel_attr = other_input.get('rel')  # 如 "q9_9"
                if rel_attr:
                    other_checkbox = div.find('input', attrs={'type': 'checkbox', 'id': rel_attr})
                    if other_checkbox:
                        raw_value = other_checkbox.get('value')
                        if raw_value is not None:
                            try:
                                metadata['other_option_value'] = int(raw_value)
                            except ValueError:
                                metadata['other_option_value'] = raw_value

        # 只读文本输入框
        if question_type == QuestionType.TEXT:
            text_input = div.find('input', attrs={'type': 'text', 'readonly': True})
            if text_input:
                metadata['readonly'] = True

        return metadata

    def _count_types(self, questions: List[Question]) -> Dict[str, int]:
        """统计各题型的数量

        Args:
            questions: 题目列表

        Returns:
            题型统计字典
        """
        counts = {}
        for question in questions:
            type_name = question.type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts

    def _extract_weight_options(self, div: Tag) -> List[Dict[str, Any]]:
        """提取权重题选项

        权重题 HTML 结构：标题行 (<td class="title">) 与 input 行交替出现

        Returns:
            选项列表，如 [{"value": 1, "label": "菜品口味"}, ...]
        """
        options = []

        table = div.find('table')
        if not table:
            return options

        rows = table.find_all('tr')
        option_index = 1
        pending_label = None

        for row in rows:
            # 标题行：有 <td class="title"> 但没有 input
            title_td = row.find('td', class_='title')
            if title_td and not row.find('input', class_='ui-slider-input'):
                pending_label = title_td.get_text(strip=True)
                continue

            # 数据行：有 ui-slider-input
            input_elem = row.find('input', class_='ui-slider-input')
            if input_elem:
                label = pending_label or f"项目{option_index}"
                options.append({"value": option_index, "label": label})
                option_index += 1
                pending_label = None

        return options
