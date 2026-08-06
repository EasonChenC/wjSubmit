# persona_generator.py
"""
受访者画像生成器

根据问卷的心理维度，生成符合现实分布的虚拟受访者画像。

核心功能：
1. 分析问卷，提取心理维度
2. 生成人口统计特征（性别、年龄、学历等）
3. 为每个维度生成base_score（遵循正态分布）
4. 生成答题风格（一致性水平、极端倾向等）

生成策略：
- 人口统计特征：根据中国人口统计数据分布
- 维度倾向：正态分布 N(μ=3.5, σ=0.8) for 5点量表
- 一致性水平：高一致性（0.75-0.9），确保α≥0.8
"""

import random
from typing import Dict, List, Optional
from core.persona import (
    Persona,
    Demographic,
    DimensionTendency,
    ResponseStyle,
    Gender,
    EducationLevel,
    IncomeLevel,
)
from core.schema import QuestionnaireSchema, QuestionType


class PersonaGenerator:
    """受访者画像生成器

    根据问卷Schema生成虚拟受访者画像。
    """

    def __init__(self, seed: Optional[int] = None):
        """初始化生成器

        Args:
            seed: 随机种子，用于可复现的生成（可选）
        """
        if seed is not None:
            random.seed(seed)

    def generate(self, schema: QuestionnaireSchema, persona_id: str) -> Persona:
        """生成一个受访者画像

        Args:
            schema: 问卷Schema
            persona_id: 画像ID

        Returns:
            Persona对象
        """
        # 1. 生成人口统计特征
        demographic = self._generate_demographic()

        # 2. 提取问卷中的心理维度
        dimensions = self._extract_dimensions(schema)

        # 3. 为每个维度生成倾向值
        dimension_tendencies = self._generate_dimension_tendencies(dimensions)

        # 4. 生成答题风格（高一致性，确保信度）
        response_style = self._generate_response_style()

        persona = Persona(
            persona_id=persona_id,
            demographic=demographic,
            dimension_tendencies=dimension_tendencies,
            response_style=response_style,
            metadata={
                'generation_method': 'normal_distribution',
                'target_alpha': 0.8,
            }
        )

        return persona

    def _generate_demographic(self) -> Demographic:
        """生成人口统计特征

        基于中国人口统计数据的简化分布。

        Returns:
            Demographic对象
        """
        # 性别分布（接近1:1）
        gender = random.choice([Gender.MALE, Gender.FEMALE])

        # 年龄分布（18-65岁，偏向年轻）
        # 使用Beta分布模拟年龄分布
        age_normalized = random.betavariate(2, 5)  # 偏向较小值
        age = int(18 + age_normalized * (65 - 18))

        # 学历分布（偏向本科）
        education_weights = [
            (EducationLevel.HIGH_SCHOOL, 0.2),
            (EducationLevel.ASSOCIATE, 0.15),
            (EducationLevel.BACHELOR, 0.5),
            (EducationLevel.MASTER, 0.12),
            (EducationLevel.DOCTORATE, 0.03),
        ]
        education = random.choices(
            [e for e, _ in education_weights],
            weights=[w for _, w in education_weights]
        )[0]

        # 收入水平分布（偏向中等）
        income_weights = [
            (IncomeLevel.LOW, 0.15),
            (IncomeLevel.MEDIUM_LOW, 0.25),
            (IncomeLevel.MEDIUM, 0.35),
            (IncomeLevel.MEDIUM_HIGH, 0.15),
            (IncomeLevel.HIGH, 0.1),
        ]
        income = random.choices(
            [i for i, _ in income_weights],
            weights=[w for _, w in income_weights]
        )[0]

        return Demographic(
            gender=gender,
            age=age,
            education=education,
            income=income,
        )

    def _extract_dimensions(self, schema: QuestionnaireSchema) -> List[Dict[str, any]]:
        """从问卷Schema中提取心理维度

        Args:
            schema: 问卷Schema

        Returns:
            维度列表，每个元素包含: {
                'name': 维度名称,
                'scale_min': 量表最小值,
                'scale_max': 量表最大值,
                'question_ids': 该维度的题目ID列表
            }
        """
        dimensions = []

        # 收集所有量表题
        scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX]
        scale_questions = [q for q in schema.questions if q.type in scale_types]

        if not scale_questions:
            return dimensions

        # 策略1: 如果schema.metadata中有dimensions映射，使用它
        if 'dimensions' in schema.metadata and schema.metadata['dimensions']:
            dimension_mapping = schema.metadata['dimensions']

            for dim_name, question_ids in dimension_mapping.items():
                # 找到第一个有效题目，获取量表范围
                scale_min, scale_max = 1, 5  # 默认值
                for qid in question_ids:
                    q = schema.get_question_by_id(qid)
                    if q and q.options:
                        if q.type == QuestionType.NPS:
                            scale_min, scale_max = 0, 10
                        elif q.type in [QuestionType.RATING, QuestionType.MATRIX]:
                            scale_min = min(q.options) if isinstance(q.options[0], int) else 1
                            scale_max = max(q.options) if isinstance(q.options[0], int) else 5
                        break

                dimensions.append({
                    'name': dim_name,
                    'scale_min': scale_min,
                    'scale_max': scale_max,
                    'question_ids': question_ids,
                })

        # 策略2: 如果没有维度映射，创建一个默认的"整体评价"维度
        else:
            # 按题型分组
            rating_questions = [q.id for q in scale_questions if q.type == QuestionType.RATING]
            nps_questions = [q.id for q in scale_questions if q.type == QuestionType.NPS]
            matrix_questions = [q.id for q in scale_questions if q.type == QuestionType.MATRIX]

            if rating_questions:
                dimensions.append({
                    'name': '整体评价',
                    'scale_min': 1,
                    'scale_max': 5,
                    'question_ids': rating_questions,
                })

            if nps_questions:
                dimensions.append({
                    'name': '推荐意愿',
                    'scale_min': 0,
                    'scale_max': 10,
                    'question_ids': nps_questions,
                })

            if matrix_questions:
                dimensions.append({
                    'name': '多维度评价',
                    'scale_min': 1,
                    'scale_max': 5,
                    'question_ids': matrix_questions,
                })

        return dimensions

    def _generate_dimension_tendencies(
        self,
        dimensions: List[Dict[str, any]]
    ) -> Dict[str, DimensionTendency]:
        """为每个维度生成倾向值

        使用正态分布生成base_score，确保：
        1. 分数偏向正面（μ略高于中位数）
        2. 有一定波动范围（σ适中）
        3. 不同维度之间有一定相关性（模拟真实受访者）

        Args:
            dimensions: 维度列表

        Returns:
            维度倾向字典
        """
        tendencies = {}

        # 生成全局倾向偏差（模拟受访者的整体正向/负向倾向）
        # -1.0 到 1.0，表示相对于均值的偏移
        global_bias = random.gauss(0, 0.3)
        global_bias = max(-1.0, min(1.0, global_bias))

        for dim in dimensions:
            scale_min = dim['scale_min']
            scale_max = dim['scale_max']
            scale_range = scale_max - scale_min

            # 计算该量表的中位数和标准差
            scale_mid = (scale_min + scale_max) / 2

            # 目标均值：略高于中位数（模拟正向偏差）
            target_mean = scale_mid + 0.3 * scale_range

            # 标准差：约为量表范围的20%
            target_std = 0.2 * scale_range

            # 应用全局偏差
            adjusted_mean = target_mean + global_bias * 0.5 * scale_range

            # 生成base_score（正态分布）
            base_score = random.gauss(adjusted_mean, target_std)

            # 限制在量表范围内，留出一定波动空间
            variance = 0.8  # 波动范围
            min_allowed = scale_min + variance * 0.5
            max_allowed = scale_max - variance * 0.5
            base_score = max(min_allowed, min(max_allowed, base_score))

            tendency = DimensionTendency(
                dimension_name=dim['name'],
                base_score=base_score,
                scale_min=scale_min,
                scale_max=scale_max,
                variance=variance,
            )

            tendencies[dim['name']] = tendency

        return tendencies

    def _generate_response_style(self) -> ResponseStyle:
        """生成答题风格

        为确保高信度（α≥0.8），需要高一致性水平。

        Returns:
            ResponseStyle对象
        """
        # 极端倾向：10%-40%之间
        extreme_tendency = random.uniform(0.1, 0.4)

        # 中立回避：50%-80%之间
        neutral_avoidance = random.uniform(0.5, 0.8)

        # 一致性水平：75%-90%之间（高一致性确保信度）
        consistency_level = random.uniform(0.75, 0.9)

        # 答题速度：随机选择
        response_speed = random.choice(["fast", "medium", "slow"])

        return ResponseStyle(
            extreme_tendency=extreme_tendency,
            neutral_avoidance=neutral_avoidance,
            consistency_level=consistency_level,
            response_speed=response_speed,
        )

    def generate_batch(
        self,
        schema: QuestionnaireSchema,
        count: int,
        id_prefix: str = "persona"
    ) -> List[Persona]:
        """批量生成受访者画像

        Args:
            schema: 问卷Schema
            count: 生成数量
            id_prefix: ID前缀

        Returns:
            Persona对象列表
        """
        personas = []
        for i in range(count):
            persona_id = f"{id_prefix}_{i+1:04d}"
            persona = self.generate(schema, persona_id)
            personas.append(persona)

        return personas
