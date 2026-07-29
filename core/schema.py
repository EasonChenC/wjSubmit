# schema.py
"""
问卷结构抽象层

定义问卷、题目、选择器、答案策略等核心数据结构，
用于统一表示不同平台、不同题型的问卷。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Union


class QuestionType(Enum):
    """题型枚举"""
    RADIO = "radio"              # 单选题
    CHECKBOX = "checkbox"        # 多选题
    SELECT = "select"            # 下拉选择题
    TEXT = "text"                # 文本输入题
    TEXTAREA = "textarea"        # 多行文本题
    MATRIX = "matrix"            # 矩阵评分题
    RATING = "rating"            # 评分题（1-5星）
    NPS = "nps"                  # NPS推荐度（0-10分）
    SORT = "sort"                # 排序题
    UNKNOWN = "unknown"          # 未识别题型


@dataclass
class SelectorConfig:
    """选择器配置

    定义如何在页面上定位和操作该题目的元素。

    Attributes:
        template: 选择器模板，使用{id}和{value}作为占位符
                 例如: ".label[for='q{id}_{value}']"
        container: 容器选择器，用于限定查找范围
                  例如: "#div{id}"
        special_handling: 特殊处理标记，用于需要特殊逻辑的题型
                         例如: "nps_val_offset", "readonly_input"
    """
    template: str
    container: Optional[str] = None
    special_handling: Optional[str] = None

    def format_selector(self, question_id: str, value: Any = None, **kwargs) -> str:
        """格式化选择器

        Args:
            question_id: 题目ID，如 "q1"
            value: 选项值，如 "1"、"2"
            **kwargs: 其他格式化参数，如 row="0"

        Returns:
            格式化后的选择器字符串
        """
        params = {'id': question_id}
        if value is not None:
            params['value'] = value
        params.update(kwargs)

        selector = self.template.format(**params)

        if self.container:
            container = self.container.format(**params)
            return f"{container} {selector}"

        return selector


@dataclass
class AnswerStrategy:
    """答案生成策略

    定义如何为该题目生成答案。

    Attributes:
        type: 策略类型
            - "weighted_random": 带权重的随机选择
            - "random_sample": 随机抽样（多选）
            - "random_shuffle": 随机打乱（排序）
            - "random_int": 随机整数（评分）
            - "text_pool": 从文本池中选择
            - "faker": 使用Faker生成
        params: 策略参数，根据type不同而不同
    """
    type: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Question:
    """题目定义

    表示问卷中的一个题目。

    Attributes:
        id: 题目ID，如 "q1", "q7_0"（矩阵题的行）
        type: 题型
        label: 题目文本
        options: 选项列表，格式根据题型不同：
                - 单选/多选: [1, 2, 3]
                - 下拉: [1, 2, 3, 4, 5]
                - 评分: [1, 2, 3, 4, 5]
                - NPS: [0, 1, 2, ..., 10]
                - 排序: [1, 2, 3, 4, 5, 6]（serial值）
                - 文本: []（空列表）
        selector: 填写选择器配置
        strategy: 答案生成策略
        required: 是否必填
        metadata: 额外元数据，如 {"other_text_id": "tqq9_8"}
    """
    id: str
    type: QuestionType
    label: str
    options: List[Any]
    selector: SelectorConfig
    strategy: AnswerStrategy
    required: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Question(id={self.id}, type={self.type.value}, label={self.label[:20]}...)"


@dataclass
class QuestionnaireSchema:
    """问卷结构定义

    表示一份完整的问卷。

    Attributes:
        url: 问卷URL
        activity_id: 活动ID，从URL中提取，如 "rqKTYry"
        platform: 平台标识，如 "wjx" (问卷星)、"wjcn" (问卷网)
        questions: 题目列表
        metadata: 元数据，包含问卷的额外信息
    """
    url: str
    activity_id: str
    platform: str
    questions: List[Question]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_question_by_id(self, question_id: str) -> Optional[Question]:
        """根据ID获取题目"""
        for question in self.questions:
            if question.id == question_id:
                return question
        return None

    def get_questions_by_type(self, question_type: QuestionType) -> List[Question]:
        """获取指定类型的所有题目"""
        return [q for q in self.questions if q.type == question_type]

    def __repr__(self) -> str:
        return (f"QuestionnaireSchema(url={self.url}, "
                f"platform={self.platform}, "
                f"questions={len(self.questions)})")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'url': self.url,
            'activity_id': self.activity_id,
            'platform': self.platform,
            'questions': [
                {
                    'id': q.id,
                    'type': q.type.value,
                    'label': q.label,
                    'options': q.options,
                    'selector': {
                        'template': q.selector.template,
                        'container': q.selector.container,
                        'special_handling': q.selector.special_handling,
                    },
                    'strategy': {
                        'type': q.strategy.type,
                        'params': q.strategy.params,
                    },
                    'required': q.required,
                    'metadata': q.metadata,
                }
                for q in self.questions
            ],
            'metadata': self.metadata,
        }


# 预定义的选择器模板（基于skill.md）
SELECTOR_TEMPLATES = {
    QuestionType.RADIO: SelectorConfig(
        template='.label[for="q{id}_{value}"]',
        special_handling=None
    ),
    QuestionType.CHECKBOX: SelectorConfig(
        template='.label[for="q{id}_{value}"]',
        special_handling=None
    ),
    QuestionType.SELECT: SelectorConfig(
        template='select[name="q{id}"]',
        special_handling=None
    ),
    QuestionType.TEXT: SelectorConfig(
        template='#q{id}',
        special_handling="use_js_setvalue"  # 需要用JS设置值
    ),
    QuestionType.TEXTAREA: SelectorConfig(
        template='textarea#q{id}',
        special_handling=None
    ),
    QuestionType.MATRIX: SelectorConfig(
        template='a[dval="{value}"]',
        container='tr[fid="q{id}_{row}"]',
        special_handling=None
    ),
    QuestionType.RATING: SelectorConfig(
        template='a.rate-off[val="{value}"]',
        container='#div{id}',
        special_handling=None
    ),
    QuestionType.NPS: SelectorConfig(
        template='a.rate-off[val="{value}"]',
        container='#div{id}',
        special_handling="nps_val_offset"  # val = value + 1
    ),
    QuestionType.SORT: SelectorConfig(
        template='li.ui-li-static[serial="{value}"]',
        container='#div{id}',
        special_handling="sequential_click"  # 需要依次点击
    ),
}


# 预定义的答案策略模板
STRATEGY_TEMPLATES = {
    QuestionType.RADIO: AnswerStrategy(
        type="weighted_random",
        params={"weights": None}  # 将在分析时填充
    ),
    QuestionType.CHECKBOX: AnswerStrategy(
        type="random_sample",
        params={"min": 2, "max": 4}
    ),
    QuestionType.SELECT: AnswerStrategy(
        type="weighted_random",
        params={"weights": None}
    ),
    QuestionType.TEXT: AnswerStrategy(
        type="text_pool",
        params={"pool": []}
    ),
    QuestionType.TEXTAREA: AnswerStrategy(
        type="text_pool",
        params={"pool": [], "optional_rate": 0.2}
    ),
    QuestionType.MATRIX: AnswerStrategy(
        type="random_int",
        params={"min": 3, "max": 5}
    ),
    QuestionType.RATING: AnswerStrategy(
        type="weighted_random",
        params={"weights": [0.02, 0.05, 0.15, 0.38, 0.40]}  # 倾向高分
    ),
    QuestionType.NPS: AnswerStrategy(
        type="weighted_random",
        params={
            "weights": [0.01, 0.01, 0.02, 0.03, 0.05, 0.08,
                       0.1, 0.15, 0.2, 0.2, 0.15]  # 0-10分
        }
    ),
    QuestionType.SORT: AnswerStrategy(
        type="random_shuffle",
        params={}
    ),
}
