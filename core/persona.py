# persona.py
"""
受访者画像系统

定义虚拟受访者的人物特征和心理倾向，确保同一受访者在相关题目上的答案具有内在一致性。

核心概念：
- Persona: 虚拟受访者，包含人口统计特征、心理维度倾向、答题风格
- DimensionTendency: 某个心理维度的倾向，如满意度=4.2分（基础分）
- ResponseStyle: 答题风格，如极端倾向、中立回避、一致性水平
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class Gender(Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class EducationLevel(Enum):
    """学历"""
    HIGH_SCHOOL = "high_school"       # 高中及以下
    ASSOCIATE = "associate"            # 专科/大专
    BACHELOR = "bachelor"              # 本科
    MASTER = "master"                  # 硕士
    DOCTORATE = "doctorate"            # 博士


class IncomeLevel(Enum):
    """收入水平"""
    LOW = "low"                # 低收入（<5k/月）
    MEDIUM_LOW = "medium_low"  # 中低收入（5k-10k/月）
    MEDIUM = "medium"          # 中等收入（10k-20k/月）
    MEDIUM_HIGH = "medium_high" # 中高收入（20k-30k/月）
    HIGH = "high"              # 高收入（>30k/月）


@dataclass
class Demographic:
    """人口统计特征

    描述虚拟受访者的基本人口统计信息。

    Attributes:
        gender: 性别
        age: 年龄（岁）
        education: 学历
        income: 收入水平
        occupation: 职业（可选）
    """
    gender: Gender
    age: int
    education: EducationLevel
    income: IncomeLevel
    occupation: Optional[str] = None

    def __repr__(self) -> str:
        return (f"Demographic(gender={self.gender.value}, age={self.age}, "
                f"education={self.education.value}, income={self.income.value})")


@dataclass
class DimensionTendency:
    """心理维度倾向

    表示受访者在某个心理维度上的倾向值。

    Attributes:
        dimension_name: 维度名称，如"满意度"、"忠诚度"
        base_score: 基础分（如4.2），所有该维度的题目围绕此分数波动
        scale_min: 量表最小值（如1）
        scale_max: 量表最大值（如5）
        variance: 允许的随机波动范围（如0.8）

    Example:
        满意度维度：base_score=4.2, scale_min=1, scale_max=5, variance=0.8
        → 该受访者在满意度相关题目上会答3.4-5.0之间的分数
    """
    dimension_name: str
    base_score: float
    scale_min: int
    scale_max: int
    variance: float = 0.8  # 默认波动范围

    def __repr__(self) -> str:
        return f"DimensionTendency({self.dimension_name}={self.base_score:.2f}, range=[{self.scale_min}, {self.scale_max}])"


@dataclass
class ResponseStyle:
    """答题风格

    描述受访者的答题习惯和倾向。

    Attributes:
        extreme_tendency: 极端倾向（0-1），值越大越倾向选择极端选项（1分或5分）
        neutral_avoidance: 中立回避（0-1），值越大越倾向避免中立选项（3分）
        consistency_level: 一致性水平（0-1），值越大答题越一致（波动越小）
        response_speed: 答题速度倾向（快/中/慢），影响时间戳生成

    Example:
        ResponseStyle(extreme_tendency=0.3, neutral_avoidance=0.7, consistency_level=0.85)
        → 30%概率选极端选项，70%概率避开中立，高一致性（波动小）
    """
    extreme_tendency: float = 0.2      # 默认20%极端倾向
    neutral_avoidance: float = 0.6     # 默认60%中立回避
    consistency_level: float = 0.8     # 默认80%一致性
    response_speed: str = "medium"     # 答题速度："fast", "medium", "slow"

    def __post_init__(self):
        """验证参数范围"""
        assert 0 <= self.extreme_tendency <= 1, "extreme_tendency must be in [0, 1]"
        assert 0 <= self.neutral_avoidance <= 1, "neutral_avoidance must be in [0, 1]"
        assert 0 <= self.consistency_level <= 1, "consistency_level must be in [0, 1]"
        assert self.response_speed in ["fast", "medium", "slow"], "response_speed must be 'fast', 'medium', or 'slow'"

    def __repr__(self) -> str:
        return (f"ResponseStyle(extreme={self.extreme_tendency:.2f}, "
                f"neutral_avoid={self.neutral_avoidance:.2f}, "
                f"consistency={self.consistency_level:.2f})")


@dataclass
class Persona:
    """受访者画像

    表示一个虚拟受访者的完整特征。

    Attributes:
        persona_id: 画像ID，唯一标识（如"persona_001"）
        demographic: 人口统计特征
        dimension_tendencies: 心理维度倾向字典
                             key: 维度名称（如"满意度"）
                             value: DimensionTendency对象
        response_style: 答题风格
        metadata: 额外元数据（可选）

    Example:
        persona = Persona(
            persona_id="persona_001",
            demographic=Demographic(gender=Gender.MALE, age=28, ...),
            dimension_tendencies={
                "满意度": DimensionTendency("满意度", base_score=4.2, ...),
                "忠诚度": DimensionTendency("忠诚度", base_score=3.8, ...),
            },
            response_style=ResponseStyle(extreme_tendency=0.3, ...),
        )
    """
    persona_id: str
    demographic: Demographic
    dimension_tendencies: Dict[str, DimensionTendency]
    response_style: ResponseStyle
    metadata: Dict = field(default_factory=dict)

    def get_dimension_tendency(self, dimension_name: str) -> Optional[DimensionTendency]:
        """获取指定维度的倾向

        Args:
            dimension_name: 维度名称，如"满意度"

        Returns:
            DimensionTendency对象，如果不存在则返回None
        """
        return self.dimension_tendencies.get(dimension_name)

    def has_dimension(self, dimension_name: str) -> bool:
        """检查是否包含指定维度

        Args:
            dimension_name: 维度名称

        Returns:
            True如果包含该维度，否则False
        """
        return dimension_name in self.dimension_tendencies

    def __repr__(self) -> str:
        dimensions_str = ", ".join(self.dimension_tendencies.keys())
        return (f"Persona(id={self.persona_id}, "
                f"demographic={self.demographic.gender.value}/{self.demographic.age}岁, "
                f"dimensions=[{dimensions_str}])")
