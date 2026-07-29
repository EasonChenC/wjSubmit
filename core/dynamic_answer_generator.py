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


class DynamicAnswerGenerator:
    """动态答案生成器

    根据问卷Schema自动生成答案，支持9种题型。
    """

    def __init__(self, schema: QuestionnaireSchema):
        """初始化生成器

        Args:
            schema: 问卷结构定义
        """
        self.schema = schema

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

        else:
            # UNKNOWN类型，返回None
            return None

    def _generate_radio_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成单选题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            选项ID，如 1, 2, 3
        """
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(question.options):
                return random.choices(question.options, weights=weights)[0]

        # 默认：均等概率随机选择
        return random.choice(question.options)

    def _generate_checkbox_answer(self, question: Question, strategy: AnswerStrategy) -> List[int]:
        """生成多选题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            选项ID列表，如 [1, 3, 5]
        """
        if strategy.type == "random_sample":
            min_choices = strategy.params.get('min', 2)
            max_choices = strategy.params.get('max', 4)

            # 确保范围合法
            min_choices = max(1, min(min_choices, len(question.options)))
            max_choices = max(min_choices, min(max_choices, len(question.options)))

            # 随机选择数量
            num_choices = random.randint(min_choices, max_choices)

            # 随机抽样
            return sorted(random.sample(question.options, num_choices))

        # 默认：随机选择2-3个
        num_choices = random.randint(2, min(3, len(question.options)))
        return sorted(random.sample(question.options, num_choices))

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
        if strategy.type == "random_int":
            min_val = strategy.params.get('min', 3)
            max_val = strategy.params.get('max', 5)

            # 从options中筛选出在范围内的值
            valid_options = [opt for opt in question.options
                           if int(opt) >= min_val and int(opt) <= max_val]

            if valid_options:
                return random.choice(valid_options)

        # 默认：从所有选项中随机选择，倾向高分
        if len(question.options) >= 3:
            # 80%概率选择后3个（高分）
            if random.random() < 0.8:
                return random.choice(question.options[-3:])

        return random.choice(question.options)

    def _generate_rating_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成评分题答案（1-5分）

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            评分值，如 1, 2, 3, 4, 5
        """
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(question.options):
                return random.choices(question.options, weights=weights)[0]

        # 默认：倾向高分（4-5分占80%）
        if random.random() < 0.8:
            # 高分
            high_scores = [opt for opt in question.options if int(opt) >= 4]
            if high_scores:
                return random.choice(high_scores)

        return random.choice(question.options)

    def _generate_nps_answer(self, question: Question, strategy: AnswerStrategy) -> int:
        """生成NPS推荐度答案（0-10分）

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            推荐度分值，如 7, 8, 9, 10
        """
        if strategy.type == "weighted_random":
            weights = strategy.params.get('weights')
            if weights and len(weights) == len(question.options):
                return random.choices(question.options, weights=weights)[0]

        # 默认：倾向推荐（7-10分占70%）
        if random.random() < 0.7:
            promoters = [opt for opt in question.options if int(opt) >= 7]
            if promoters:
                return random.choice(promoters)

        return random.choice(question.options)

    def _generate_sort_answer(self, question: Question, strategy: AnswerStrategy) -> List[int]:
        """生成排序题答案

        Args:
            question: 题目对象
            strategy: 答案策略

        Returns:
            排序后的serial值列表，如 [3, 1, 5, 2, 4, 6]
        """
        # 随机打乱选项顺序
        shuffled = question.options.copy()
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
