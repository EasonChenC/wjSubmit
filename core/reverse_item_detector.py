# reverse_item_detector.py
"""
反向题识别器

基于NLP关键词匹配和语义分析识别量表题中的反向题。
反向题是指在问卷中故意设置的与正向题相反的题目，用于检测答题者的一致性。

示例：
- 正向题：我对产品非常满意
- 反向题：我对产品感到失望
"""

import re
from typing import List, Tuple, Dict
from dataclasses import dataclass

from utils.scale_utils import split_scale_values, extract_option_values


@dataclass
class ReversePattern:
    """反向题识别模式"""
    keywords: List[str]        # 关键词列表
    pattern: str               # 正则表达式模式
    weight: float              # 权重（0-1）
    context: str               # 上下文类型


class ReverseItemDetector:
    """反向题识别器

    基于关键词匹配和语义分析识别量表题中的反向题
    """

    def __init__(self):
        # 负面词汇模式
        self.negative_patterns = [
            ReversePattern(
                keywords=['不', '没有', '缺乏', '缺少', '无', '不愿意'],
                pattern=r'(不(?!.*不)|没有|缺乏|缺少|无(?!限|数|疑|奈|论|关)|不愿意)',
                weight=0.8,
                context='negation'
            ),
            ReversePattern(
                keywords=['难以', '很少', '从不', '极少', '罕见', '从未', '不会'],
                pattern=r'(难以|很少|从不|极少|罕见|从未|不会)',
                weight=0.9,
                context='frequency_negation'
            ),
            ReversePattern(
                keywords=['失望', '不满', '沮丧', '担心', '焦虑', '失败', '糟糕'],
                pattern=r'(失望|不满|沮丧|担心|焦虑|失败|糟糕)',
                weight=0.85,
                context='negative_emotion'
            ),
            ReversePattern(
                keywords=['讨厌', '反对', '拒绝', '厌恶', '抗拒', '抵触'],
                pattern=r'(讨厌|反对|拒绝|厌恶|抗拒|抵触)',
                weight=0.85,
                context='negative_attitude'
            ),
            ReversePattern(
                keywords=['困难', '麻烦', '问题', '障碍', '阻碍', '困扰', '缺陷', '毛病'],
                pattern=r'(困难|麻烦|问题|障碍|阻碍|困扰|缺陷|毛病)',
                weight=0.7,
                context='negative_state'
            ),
            ReversePattern(
                keywords=['差', '劣', '低', '弱', '不好', '不佳', '不足'],
                pattern=r'(差|劣|低(?!于)|弱|不好|不佳|不足)',
                weight=0.8,
                context='negative_evaluation'
            ),
            ReversePattern(
                keywords=['怀疑', '质疑', '不信', '不相信'],
                pattern=r'(怀疑|质疑|不信|不相信)',
                weight=0.85,
                context='negative_trust'
            ),
        ]

        # 排除模式（包含负面词但不是反向题）
        self.exclusion_patterns = [
            r'不.*不',  # 双重否定："不会不满意"
            r'解决.*问题',  # "解决问题"是正向
            r'克服.*困难',  # "克服困难"是正向
            r'消除.*障碍',  # "消除障碍"是正向
            r'避免.*麻烦',  # "避免麻烦"是正向
            r'减少.*担心',  # "减少担心"是正向
            r'没有.*问题',  # "没有问题"是正向
        ]

    def detect(self, question_label: str) -> Tuple[bool, float, List[str]]:
        """检测题目是否为反向题

        Args:
            question_label: 题目文本

        Returns:
            (is_reverse, confidence, matched_keywords)
            - is_reverse: 是否为反向题
            - confidence: 置信度（0-1）
            - matched_keywords: 匹配的关键词列表
        """
        # 检查排除模式
        for exclusion in self.exclusion_patterns:
            if re.search(exclusion, question_label):
                return False, 0.0, []

        # 匹配负面模式
        matched_keywords = []
        matched_weight = 0.0
        matched_contexts = set()

        for pattern in self.negative_patterns:
            if re.search(pattern.pattern, question_label):
                matched_keywords.extend(pattern.keywords)
                matched_weight += pattern.weight
                matched_contexts.add(pattern.context)

        # 计算置信度
        if not matched_keywords:
            return False, 0.0, []

        # 基础置信度 = 匹配权重归一化
        base_confidence = min(1.0, matched_weight / 2.0)

        # 如果匹配到多个不同类型的负面模式，增加置信度
        if len(matched_contexts) >= 2:
            base_confidence = min(1.0, base_confidence * 1.2)

        # 如果匹配到多个负面词，增加置信度
        unique_keywords = set(matched_keywords)
        if len(unique_keywords) >= 3:
            base_confidence = min(1.0, base_confidence * 1.15)

        # 置信度阈值
        is_reverse = base_confidence >= 0.45

        return is_reverse, base_confidence, list(unique_keywords)

    def batch_detect(self, questions: List) -> Dict[str, Tuple[bool, float, List[str]]]:
        """批量检测反向题

        RATING/NPS/MATRIX为天然量表题（is_scale=True），据此推导
        positive_values/negative_values/neutral_values。
        RADIO题是否为量表题无法仅凭关键词判断（如"就餐时段"这类选项虽为数字
        编码但并非强度量表），因此保持原有行为：只做反向检测，不强制标记
        is_scale，交由AI识别决定。

        写入Question.metadata：
        - is_scale: 是否为量表题（RADIO默认不设置，保持False语义）
        - is_reverse: 是否为反向题（默认False，即正向）
        - reverse_confidence / reverse_keywords: 检测依据
        - positive_values / negative_values / neutral_values: 推导出的态度值（仅量表题）
        - detection_method: 'keyword'

        Args:
            questions: Question对象列表

        Returns:
            Dict[question_id, (is_reverse, confidence, keywords)]
        """
        results = {}
        native_scale_types = {'rating', 'nps', 'matrix'}

        for q in questions:
            if q.type.value not in native_scale_types | {'radio'}:
                continue

            is_rev, conf, keywords = self.detect(q.label)
            results[q.id] = (is_rev, conf, keywords)

            q.metadata['detection_method'] = 'keyword'
            q.metadata['is_reverse'] = is_rev
            q.metadata['reverse_confidence'] = conf
            q.metadata['reverse_keywords'] = keywords

            if q.type.value in native_scale_types:
                option_values = extract_option_values(q.options)
                positive, negative, neutral = split_scale_values(option_values, is_reverse=is_rev)

                q.metadata['is_scale'] = True
                q.metadata['positive_values'] = positive
                q.metadata['negative_values'] = negative
                q.metadata['neutral_values'] = neutral
            else:
                # RADIO: 是否为量表题交由AI判断，关键字模式下保持默认False
                q.metadata.setdefault('is_scale', False)

        return results

    def get_detection_report(self, questions: List) -> str:
        """生成反向题检测报告

        Args:
            questions: Question对象列表

        Returns:
            报告文本
        """
        results = self.batch_detect(questions)

        report_lines = []
        report_lines.append("=" * 60)
        report_lines.append("反向题检测报告")
        report_lines.append("=" * 60)
        report_lines.append("")

        reverse_items = [(qid, data) for qid, data in results.items() if data[0]]

        if not reverse_items:
            report_lines.append("未检测到反向题")
        else:
            report_lines.append(f"检测到 {len(reverse_items)} 个反向题：")
            report_lines.append("")

            for qid, (is_rev, conf, keywords) in reverse_items:
                # 查找对应的Question对象
                question = next((q for q in questions if q.id == qid), None)
                if question:
                    report_lines.append(f"题目ID: {qid}")
                    report_lines.append(f"题目内容: {question.label}")
                    report_lines.append(f"置信度: {conf:.2f}")
                    report_lines.append(f"匹配关键词: {', '.join(keywords)}")
                    report_lines.append("-" * 60)

        report_lines.append("")
        report_lines.append(f"总题目数: {len(questions)}")
        report_lines.append(f"反向题数量: {len(reverse_items)}")
        report_lines.append(f"反向题比例: {len(reverse_items)/len(questions)*100:.1f}%")
        report_lines.append("=" * 60)

        return "\n".join(report_lines)


class EnhancedReverseDetector(ReverseItemDetector):
    """增强型反向题识别器

    在基础识别器基础上增加：
    1. 同维度题目对比分析
    2. 手动标注优先策略
    """

    def detect_by_dimension_contrast(self,
                                    target_question: str,
                                    dimension_questions: List[str]) -> float:
        """通过同维度题目对比判断是否为反向题

        原理：反向题与同维度其他题目的语义方向相反

        Args:
            target_question: 目标题目文本
            dimension_questions: 同维度的其他题目文本列表

        Returns:
            反向概率（0-1）
        """
        # 检查目标题是否包含负面词
        target_has_negative = any(
            re.search(p.pattern, target_question)
            for p in self.negative_patterns
        )

        # 检查其他题目中有多少包含负面词
        others_negative_count = sum(
            any(re.search(p.pattern, q) for p in self.negative_patterns)
            for q in dimension_questions
        )

        # 如果目标题有负面词，但其他题都没有 -> 很可能是反向题
        if target_has_negative and others_negative_count == 0:
            return 0.85

        # 如果目标题没有负面词，但其他题都有 -> 可能不是反向题
        if not target_has_negative and others_negative_count == len(dimension_questions):
            return 0.15

        # 不确定
        return 0.5

    def detect_with_manual_override(self,
                                   question,
                                   manual_reverse_items: List[str] = None) -> Tuple[bool, float, List[str]]:
        """支持手动标注覆盖的检测

        Args:
            question: Question对象
            manual_reverse_items: 手动标注的反向题ID列表

        Returns:
            (is_reverse, confidence, keywords)
        """
        # 如果有手动标注，优先使用
        if manual_reverse_items and question.id in manual_reverse_items:
            return True, 1.0, ['manual']

        # 否则使用自动检测
        return self.detect(question.label)
