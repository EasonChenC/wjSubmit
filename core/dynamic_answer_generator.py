# dynamic_answer_generator.py
"""
动态答案生成器

基于QuestionnaireSchema动态生成答案，替代硬编码的answer_generator.py。
根据题型和策略自动生成符合要求的随机答案。
"""

import random
from typing import Dict, Any, List
from datetime import datetime

from .schema import (
    QuestionnaireSchema,
    Question,
    QuestionType,
    AnswerStrategy,
)
from utils.scale_utils import split_scale_values


class DynamicAnswerGenerator:
    """动态答案生成器

    根据问卷Schema自动生成答案，支持9种题型。
    """

    @staticmethod
    def _extract_option_values(options: list) -> list:
        """从选项列表提取值

        处理两种格式：
        - 新格式: [{"value": 1, "label": "..."}, ...]
        - 旧格式: [1, 2, 3, ...]
        """
        if not options:
            return []

        first = options[0]
        if isinstance(first, dict) and "value" in first:
            # 新格式：字典with value字段
            return [opt["value"] for opt in options]
        else:
            # 旧格式：直接的值
            return list(options)

    def __init__(self, schema: QuestionnaireSchema, mode: str = "random",
                 attitude: str = "positive", add_variation: bool = False,
                 variation_ratio: float = 0.05):
        """初始化生成器

        Args:
            schema: 问卷结构定义
            mode: 提交模式，'high_reliability'（高信度）或 'random'（随机）
            attitude: 态度倾向，'positive' 或 'negative'（仅在 high_reliability 模式生效）
            add_variation: 是否添加答案变化（穿插变化）
            variation_ratio: 变化比例（0-1之间）
        """
        self.schema = schema
        self.mode = mode  # high_reliability or random
        self.attitude = attitude  # positive or negative
        self.add_variation = add_variation
        self.variation_ratio = variation_ratio

    def generate_answers(self) -> Dict[str, Any]:
        """生成所有题目的答案

        Returns:
            答案字典，格式: {'q1': 1, 'q2': 3, 'q3': '北京', ...}
        """
        answers = {}

        for question in self.schema.questions:
            answer = self._generate_answer(question)
            answers[question.id] = answer

        # 添加时间戳数据（如果需要）
        answers = self._add_timing_data(answers)

        return answers

    def _generate_answer(self, question: Question) -> Any:
        """为单个题目生成答案

        Args:
            question: 题目对象

        Returns:
            生成的答案
        """
        strategy = question.strategy

        if question.type == QuestionType.RADIO:
            return self._generate_radio_answer(question, strategy)

        elif question.type == QuestionType.CHECKBOX:
            return self._generate_checkbox_answer(question, strategy)

        elif question.type == QuestionType.SELECT:
            return self._generate_select_answer(question, strategy)

        elif question.type == QuestionType.TEXT:
            return self._generate_text_answer(question, strategy)

        elif question.type == QuestionType.TEXTAREA:
            return self._generate_textarea_answer(question, strategy)

        elif question.type == QuestionType.MATRIX:
            return self._generate_matrix_answer(question, strategy)

        elif question.type == QuestionType.RATING:
            return self._generate_rating_answer(question, strategy)

        elif question.type == QuestionType.NPS:
            return self._generate_nps_answer(question, strategy)

        elif question.type == QuestionType.SORT:
            return self._generate_sort_answer(question, strategy)

        elif question.type == QuestionType.WEIGHT:
            return self._generate_weight_answer(question, strategy)

        else:
            # UNKNOWN类型，返回None
            return None

    def _pick_by_attitude(self, question: Question, option_values: list):
        """根据 attitude 从量表题选项中挑选一个值

        优先使用 metadata 中已有的 positive_values/negative_values（AI或关键字
        检测器写入）；如果缺失（如量表题被识别但未推导态度值），现场根据选项
        数值和 is_reverse 推导，保证 attitude 在任何检测路径下都生效。

        支持穿插变化：启用时有 variation_ratio 概率忽略态度，随机选择。

        Args:
            question: 题目对象
            option_values: 该题的选项数值列表

        Returns:
            选中的值；如果无法确定量表方向（选项不足），返回 None 交由调用方 fallback
        """
        # 穿插变化：概率性随机选择，不遵循态度
        if self.add_variation and random.random() < self.variation_ratio:
            return random.choice(option_values)

        positive_values = question.metadata.get('positive_values') or []
        negative_values = question.metadata.get('negative_values') or []

        if not positive_values and not negative_values:
            is_reverse = question.metadata.get('is_reverse', False)
            positive_values, negative_values, _ = split_scale_values(option_values, is_reverse=is_reverse)

        target_values = positive_values if self.attitude == "positive" else negative_values

        if target_values:
            matching = [
                opt for opt in option_values
                if opt in target_values or str(opt) in [str(v) for v in target_values]
            ]
            if matching:
                return random.choice(matching)

        return None

    def _generate_radio_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成单选题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            选项ID，如 1, 2, 3
        """
        option_values = self._extract_option_values(question.options)
        is_scale = question.metadata.get('is_scale', False)

        # 随机模式：不考虑态度，直接随机
        if self.mode == "random":
            return random.choice(option_values)

        # 高可靠性模式：量表题根据 attitude 选择
        if is_scale:
            answer = self._pick_by_attitude(question, option_values)
            if answer is not None:
                return answer

        # 非量表题或 Fallback：使用策略
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(option_values):
                return random.choices(option_values, weights=weights)[0]

        # 默认：均等概率随机选择
        return random.choice(option_values)

    def _generate_checkbox_answer(self, question: Question, strategy: AnswerStrategy) -> List[int]:
        """生成多选题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            选项ID列表，如 [1, 3, 5]
        """
        option_values = self._extract_option_values(question.options)

        # 默认不勾选"其他"选项：勾选后问卷星会要求必须填写说明文本，
        # 自动化填写无法保证内容合理，因此从可抽样池中剔除该选项
        other_value = question.metadata.get('other_option_value')
        sampleable_values = [v for v in option_values if v != other_value] if other_value is not None else option_values
        if not sampleable_values:
            sampleable_values = option_values

        if strategy.type == "random_sample":
            min_choices = strategy.params.get('min', 2)
            max_choices = strategy.params.get('max', 4)

            # 确保范围合法（基于剔除"其他"后的可选池）
            min_choices = max(1, min(min_choices, len(sampleable_values)))
            max_choices = max(min_choices, min(max_choices, len(sampleable_values)))

            # 随机选择数量
            num_choices = random.randint(min_choices, max_choices)

            # 随机抽样
            return sorted(random.sample(sampleable_values, num_choices))

        # 默认：随机选择2-3个
        num_choices = random.randint(2, min(3, len(sampleable_values)))
        return sorted(random.sample(sampleable_values, num_choices))

    def _generate_select_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成下拉选择题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            选项值，如 1, 2, 3
        """
        # 下拉题与单选题逻辑相同
        return self._generate_radio_answer(question, strategy)

    def _generate_text_answer(self, question: Question, strategy: AnswerStrategy) -> str:
        """生成文本输入题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            文本字符串
        """
        if strategy.type == "text_pool":
            pool = strategy.params.get('pool', [])
            if pool:
                return random.choice(pool)

        # 默认文本池（通用）
        default_pool = [
            '北京', '上海', '广州', '深圳', '杭州', '南京',
            '成都', '武汉', '西安', '重庆', '天津', '苏州'
        ]
        return random.choice(default_pool)

    def _generate_textarea_answer(self, question: Question, strategy: AnswerStrategy) -> str:
        """生成多行文本题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            多行文本字符串
        """
        if strategy.type == "text_pool":
            pool = strategy.params.get('pool', [])
            if pool:
                return random.choice(pool)

        # 默认建议池
        default_suggestions = [
            '总体满意，希望能提供更多优惠活动。',
            '服务质量不错，配送速度很快。',
            '产品质量很好，性价比高，会继续购买。',
            '希望能改进客服响应速度，其他方面都挺好的。',
            '界面设计简洁，操作方便，体验良好。',
            '物流服务好，包装完整，商品质量有保障。',
            '平台活动丰富，经常有优惠券可以使用。',
            '售后服务到位，退换货流程简单快捷。',
        ]
        return random.choice(default_suggestions)

    def _generate_matrix_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成矩阵评分题答案（单行）

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            评分值，如 "3", "4", "5"
        """
        option_values = self._extract_option_values(question.options)

        # 高可靠性模式：根据态度选择积极/消极值
        if self.mode == "high_reliability":
            is_scale = question.metadata.get('is_scale', True)

            if is_scale:
                answer = self._pick_by_attitude(question, option_values)
                if answer is not None:
                    return answer

        # 随机模式或无法应用态度：自然分布随机（不代表任何态度倾向）
        if len(option_values) >= 3:
            if random.random() < 0.8:
                return random.choice(option_values[-3:])

        return random.choice(option_values)

    def _generate_rating_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成评分题答案（1-5分）

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            评分值，如 1, 2, 3, 4, 5
        """
        option_values = self._extract_option_values(question.options)

        # 高可靠性模式：根据态度选择积极/消极值
        if self.mode == "high_reliability":
            is_scale = question.metadata.get('is_scale', True)

            if is_scale:
                answer = self._pick_by_attitude(question, option_values)
                if answer is not None:
                    return answer

        # 随机模式或无法应用态度：使用策略权重（题型默认自然分布）
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(option_values):
                return random.choices(option_values, weights=weights)[0]

        if random.random() < 0.8:
            high_scores = [opt for opt in option_values if int(opt) >= 4]
            if high_scores:
                return random.choice(high_scores)

        return random.choice(option_values)

    def _generate_nps_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成NPS推荐度答案（0-10分）

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            推荐度分值，如 7, 8, 9, 10
        """
        option_values = self._extract_option_values(question.options)

        # 高可靠性模式：根据态度选择积极/消极值
        if self.mode == "high_reliability":
            is_scale = question.metadata.get('is_scale', True)

            if is_scale:
                answer = self._pick_by_attitude(question, option_values)
                if answer is not None:
                    return answer

        # 随机模式或无法应用态度：使用策略权重（题型默认自然分布）
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(option_values):
                return random.choices(option_values, weights=weights)[0]

        return random.choice(option_values)

    def _generate_sort_answer(self, question: Question, strategy: AnswerStrategy) -> List[int]:
        """生成排序题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            排序后的serial值列表，如 [3, 1, 5, 2, 4, 6]
        """
        option_values = self._extract_option_values(question.options)
        # 随机打乱选项顺序
        shuffled = option_values.copy()
        random.shuffle(shuffled)
        return shuffled

    def _add_timing_data(self, answers: Dict[str, Any]) -> Dict[str, Any]:
        """添加答题时间数据

        某些问卷可能需要记录答题时间。

        Args:
            answers: 答案字典

        Returns:
            添加了时间数据的答案字典
        """
        # 生成随机答题时长（60-300秒）
        total_time = random.randint(60, 300)

        # 添加时间戳（如果需要）
        answers['__meta__'] = {
            'start_time': datetime.now().isoformat(),
            'total_time': total_time,
        }

        return answers

    def _generate_weight_answer(self, question: Question, strategy: AnswerStrategy) -> Dict[str, int]:
        """生成权重题答案

        权重题需要分配总数为100%的权重到多个因素

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            权重字典，如 {"1": 20, "2": 15, "3": 25, ...}
        """
        option_values = self._extract_option_values(question.options)
        num_items = len(option_values)

        if num_items == 0:
            return {}

        # 获取分配策略
        distribution_strategy = strategy.params.get('strategy', 'random')

        if distribution_strategy == 'even':
            # 均匀分配
            weight_per_item = 100 / num_items
            weights = {str(i + 1): int(weight_per_item) for i in range(num_items)}
            # 调整最后一项以确保总和为100
            total = sum(weights.values())
            if total != 100:
                weights[str(num_items)] += (100 - total)

        elif distribution_strategy == 'bias':
            # 倾向分配（前几项权重较高）
            if num_items == 1:
                weights = {"1": 100}
            elif num_items == 2:
                weights = {"1": 60, "2": 40}
            elif num_items == 3:
                weights = {"1": 50, "2": 30, "3": 20}
            elif num_items == 4:
                weights = {"1": 40, "2": 30, "3": 20, "4": 10}
            elif num_items == 5:
                weights = {"1": 35, "2": 25, "3": 20, "4": 15, "5": 5}
            elif num_items == 6:
                weights = {"1": 30, "2": 25, "3": 20, "4": 15, "5": 7, "6": 3}
            else:
                # 超过6项，使用随机
                return self._random_weight_distribution(num_items)

        else:  # random (默认)
            # 随机分配
            weights = self._random_weight_distribution(num_items)

        return weights

    def _random_weight_distribution(self, num_items: int) -> Dict[str, int]:
        """生成随机权重分配

        使用 stick-breaking 算法生成总和为100的随机权重

        Args:
            num_items: 权重项数量

        Returns:
            权重字典
        """
        if num_items == 1:
            return {"1": 100}

        # 生成随机权重
        random_values = [random.random() for _ in range(num_items)]
        total = sum(random_values)
        normalized = [int((val / total) * 100) for val in random_values]

        # 调整确保总和为100
        current_sum = sum(normalized)
        if current_sum != 100:
            normalized[-1] += (100 - current_sum)

        return {str(i + 1): normalized[i] for i in range(num_items)}


class TextAnswerPool:
    """文本答案池管理器

    为文本题和多行文本题提供可定制的答案池。
    可以根据题目关键词匹配不同的答案池。
    """

    def __init__(self):
        """初始化答案池"""
        self.pools = {
            # 城市相关
            'city': ['北京', '上海', '广州', '深圳', '杭州', '南京',
                    '成都', '武汉', '西安', '重庆', '天津', '苏州'],

            # 职业相关
            'occupation': ['学生', '教师', '工程师', '医生', '销售',
                          '设计师', '程序员', '公务员', '自由职业'],

            # 商品类别
            'product_category': ['服装鞋包', '数码家电', '美妆护肤', '食品饮料',
                                '图书文具', '家居日用', '运动户外', '母婴用品'],

            # 改进建议
            'suggestions': [
                '总体满意，希望能提供更多优惠活动。',
                '服务质量不错，配送速度很快。',
                '产品质量很好，性价比高，会继续购买。',
                '希望能改进客服响应速度，其他方面都挺好的。',
                '界面设计简洁，操作方便，体验良好。',
                '物流服务好，包装完整，商品质量有保障。',
                '平台活动丰富，经常有优惠券可以使用。',
                '售后服务到位，退换货流程简单快捷。',
            ],
        }

    def get(self, pool_name: str) -> List[str]:
        """获取指定答案池

        Args:
            pool_name: 答案池名称

        Returns:
            答案列表
        """
        return self.pools.get(pool_name, [])

    def add_pool(self, pool_name: str, answers: List[str]):
        """添加自定义答案池

        Args:
            pool_name: 答案池名称
            answers: 答案列表
        """
        self.pools[pool_name] = answers

    def match_pool(self, question_label: str) -> str:
        """根据题目文本匹配答案池

        Args:
            question_label: 题目文本

        Returns:
            匹配的答案池名称，未匹配返回'suggestions'
        """
        label_lower = question_label.lower()

        if '城市' in question_label or '地区' in question_label:
            return 'city'
        elif '职业' in question_label or '工作' in question_label:
            return 'occupation'
        elif '商品' in question_label or '类别' in question_label:
            return 'product_category'
        else:
            return 'suggestions'
