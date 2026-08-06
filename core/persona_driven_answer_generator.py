# persona_driven_answer_generator.py
"""
基于画像的答案生成器

继承DynamicAnswerGenerator，重写量表题的答案生成逻辑，
使用受访者画像的维度倾向值来生成高一致性的答案。

核心算法：
1. 非量表题（TEXT, CHECKBOX等）：使用父类的随机生成逻辑
2. 量表题（RATING, NPS, MATRIX）：使用画像的dimension_tendency.base_score + noise
3. 反向题：自动反向计分（5-point: 6-score, 11-point: 10-score）

示例：
    画像: dimension_tendency['满意度'].base_score = 4.2
    Q1: "我对产品很满意" (正向题) → 4.2 + noise(-0.1, 0.1) = 4.3
    Q2: "我对产品不满意" (反向题) → 6 - 4.2 + noise(-0.1, 0.1) = 1.9
"""

import random
from typing import Dict, Any, Optional
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.schema import QuestionnaireSchema, Question, QuestionType, AnswerStrategy
from core.persona import Persona, DimensionTendency


class PersonaDrivenAnswerGenerator(DynamicAnswerGenerator):
    """基于画像的答案生成器

    继承DynamicAnswerGenerator，使用受访者画像生成高信度的量表题答案。
    """

    def __init__(self, schema: QuestionnaireSchema, persona: Persona):
        """初始化生成器

        Args:
            schema: 问卷结构定义
            persona: 受访者画像
        """
        super().__init__(schema, persona=persona)  # 传递persona给父类

    def _generate_answer(self, question: Question) -> Any:
        """为单个题目生成答案（重写父类方法）

        对于量表题（RATING, NPS, MATRIX），使用画像驱动生成。
        对于其他题型，使用父类的随机生成逻辑。

        Args:
            question: 题目对象

        Returns:
            生成的答案
        """
        # 量表题：使用画像驱动生成
        if question.type in [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX]:
            return self._generate_scale_answer(question)

        # 其他题型：使用父类的随机生成逻辑
        return super()._generate_answer(question)

    def _generate_scale_answer(self, question: Question) -> Any:
        """生成量表题答案（画像驱动）

        核心算法：
        1. 查找题目所属的心理维度
        2. 获取画像在该维度的base_score
        3. 添加随机噪声（根据一致性水平控制波动范围）
        4. 如果是反向题，自动反向计分
        5. 应用答题风格（极端倾向、中立回避）
        6. 限制在量表范围内并取整

        Args:
            question: 题目对象

        Returns:
            量表分数（整数）
        """
        # 1. 获取题目的维度
        dimension_name = self._get_question_dimension(question)

        # 2. 获取画像在该维度的倾向
        tendency = self.persona.get_dimension_tendency(dimension_name)

        if not tendency:
            # 如果画像中没有该维度，使用父类的随机生成
            if question.type == QuestionType.RATING:
                return super()._generate_rating_answer(question, question.strategy)
            elif question.type == QuestionType.NPS:
                return super()._generate_nps_answer(question, question.strategy)
            elif question.type == QuestionType.MATRIX:
                return super()._generate_matrix_answer(question, question.strategy)

        # 3. 计算基础分数
        base_score = tendency.base_score

        # 4. 检查是否为反向题，如果是则先反向base_score
        #    这样可以确保反向题的base_score从一开始就是低分
        is_reverse = question.metadata.get('is_reverse', False)
        if is_reverse:
            base_score = self._reverse_score(base_score, tendency)

        # 5. 添加随机噪声（根据一致性水平控制波动）
        score = self._add_noise(base_score, tendency)

        # 6. 应用答题风格（极端倾向、中立回避）
        score = self._apply_response_style(score, tendency)

        # 7. 限制在量表范围内
        score = max(tendency.scale_min, min(tendency.scale_max, score))

        # 8. 取整并转换为选项值
        score_int = round(score)

        # 9. 确保返回的是question.options中的合法值
        return self._map_to_valid_option(score_int, question)

    def _get_question_dimension(self, question: Question) -> str:
        """获取题目所属的心理维度

        优先级：
        1. question.metadata['dimension'] - 手动标注的维度
        2. 从schema.metadata['dimensions']反向查找
        3. 使用默认维度（根据题型）

        Args:
            question: 题目对象

        Returns:
            维度名称
        """
        # 优先级1: question.metadata中的dimension字段
        if 'dimension' in question.metadata and question.metadata['dimension']:
            return question.metadata['dimension']

        # 优先级2: 从schema.metadata['dimensions']反向查找
        dimensions_mapping = self.schema.metadata.get('dimensions', {})
        for dim_name, question_ids in dimensions_mapping.items():
            if question.id in question_ids:
                return dim_name

        # 优先级3: 根据题型使用默认维度
        # 这应该与PersonaGenerator._extract_dimensions()中的逻辑一致
        if question.type == QuestionType.RATING:
            return '整体评价'
        elif question.type == QuestionType.NPS:
            return '推荐意愿'
        elif question.type == QuestionType.MATRIX:
            # 矩阵题通常有base_id
            base_id = question.metadata.get('base_id', 'unknown')
            return f'矩阵题_{base_id}'  # 如果没找到，使用base_id作为维度名

        return '未分类维度'

    def _add_noise(self, base_score: float, tendency: DimensionTendency) -> float:
        """添加随机噪声

        噪声大小由：
        1. tendency.variance - 维度的波动范围
        2. persona.response_style.consistency_level - 一致性水平

        一致性越高，噪声越小。

        Args:
            base_score: 基础分数
            tendency: 维度倾向

        Returns:
            添加噪声后的分数
        """
        consistency = self.persona.response_style.consistency_level

        # 实际方差 = 基础方差 * (1 - 一致性)
        # 例如：variance=0.8, consistency=0.85 → actual_variance=0.8*0.15=0.12
        actual_variance = tendency.variance * (1 - consistency)

        # 生成噪声（均匀分布）
        noise = random.uniform(-actual_variance, actual_variance)

        return base_score + noise

    def _reverse_score(self, score: float, tendency: DimensionTendency) -> float:
        """反向计分

        反向题的计分公式：
        - 5点量表（1-5）：reversed_score = 6 - score
        - 11点量表（0-10）：reversed_score = 10 - score
        - 通用公式：reversed_score = (scale_min + scale_max) - score

        Args:
            score: 原始分数
            tendency: 维度倾向

        Returns:
            反向计分后的分数
        """
        return (tendency.scale_min + tendency.scale_max) - score

    def _apply_response_style(self, score: float, tendency: DimensionTendency) -> float:
        """应用答题风格

        根据persona.response_style调整分数：
        1. 极端倾向（extreme_tendency）：一定概率推向极端值（min或max）
        2. 中立回避（neutral_avoidance）：一定概率避开中间值

        Args:
            score: 当前分数
            tendency: 维度倾向

        Returns:
            应用风格后的分数
        """
        style = self.persona.response_style
        scale_mid = (tendency.scale_min + tendency.scale_max) / 2

        # 1. 极端倾向：推向极端值
        if random.random() < style.extreme_tendency:
            # 判断当前分数偏向哪个极端
            if score >= scale_mid:
                # 偏向高分，推向最高分
                score = score + (tendency.scale_max - score) * 0.6
            else:
                # 偏向低分，推向最低分
                score = score - (score - tendency.scale_min) * 0.6

        # 2. 中立回避：避开中间值
        # 如果分数接近中间值，推向远离中间值的方向
        mid_tolerance = 0.5  # 中间值容忍范围
        if abs(score - scale_mid) < mid_tolerance:
            if random.random() < style.neutral_avoidance:
                # 随机推向高端或低端
                if random.random() < 0.5:
                    score = scale_mid + mid_tolerance + random.uniform(0, 0.5)
                else:
                    score = scale_mid - mid_tolerance - random.uniform(0, 0.5)

        return score

    def _map_to_valid_option(self, score_int: int, question: Question) -> Any:
        """Map score to valid option value

        question.options may be integer list, string list, or dict list.

        Args:
            score_int: Integer score
            question: Question object

        Returns:
            Valid option value
        """
        if not question.options:
            return score_int

        first_opt = question.options[0]

        if isinstance(first_opt, dict):
            # Extract values from {value, label} dicts
            values = [opt.get('value') for opt in question.options]
            try:
                int_values = [int(v) for v in values if v is not None]
                if int_values:
                    if score_int in int_values:
                        return score_int
                    closest = min(int_values, key=lambda x: abs(x - score_int))
                    return closest
            except (ValueError, TypeError):
                pass
            # Fall back to first value
            return values[0] if values else score_int

        elif isinstance(first_opt, int):
            # Integer options, direct return
            valid_options = [opt for opt in question.options if isinstance(opt, int)]
            if score_int in valid_options:
                return score_int
            else:
                # Find closest valid value
                return min(valid_options, key=lambda x: abs(x - score_int))

        elif isinstance(first_opt, str):
            # String options (e.g. matrix ['1', '2', '3', '4', '5'])
            score_str = str(score_int)
            if score_str in question.options:
                return score_str
            else:
                # Try integer comparison
                try:
                    int_options = [int(opt) for opt in question.options]
                    closest = min(int_options, key=lambda x: abs(x - score_int))
                    return str(closest)
                except (ValueError, TypeError):
                    # Cannot convert, return middle option
                    return question.options[len(question.options) // 2]

        # No options, return integer directly
        return score_int

    def generate_answers(self) -> Dict[str, Any]:
        """生成所有题目的答案（重写父类方法）

        添加画像元数据到答案中。

        Returns:
            答案字典
        """
        answers = super().generate_answers()

        # 添加画像元数据
        if '__meta__' not in answers:
            answers['__meta__'] = {}

        answers['__meta__']['persona_id'] = self.persona.persona_id
        answers['__meta__']['persona_demographic'] = {
            'gender': self.persona.demographic.gender.value,
            'age': self.persona.demographic.age,
            'education': self.persona.demographic.education.value,
            'income': self.persona.demographic.income.value,
        }
        answers['__meta__']['dimension_tendencies'] = {
            dim_name: {
                'base_score': tendency.base_score,
                'scale_range': f"[{tendency.scale_min}, {tendency.scale_max}]"
            }
            for dim_name, tendency in self.persona.dimension_tendencies.items()
        }
        answers['__meta__']['consistency_level'] = self.persona.response_style.consistency_level

        return answers
