# reliability_validator.py
"""
信效度验证器

实现Cronbach's α计算和量表信度分析。

核心功能：
1. 计算Cronbach's α（整体和分维度）
2. Item-Total Correlation（题目-总分相关性）
3. Alpha if Item Deleted（删除某题后的α）
4. 生成信度分析报告

数学原理：
    Cronbach's α = (k / (k-1)) × (1 - Σσᵢ² / σₜ²)
    其中：
    - k = 题目数量
    - σᵢ² = 第i题的方差
    - σₜ² = 总分的方差
"""

import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from core.schema import QuestionnaireSchema, Question, QuestionType


@dataclass
class ReliabilityResult:
    """信度分析结果

    Attributes:
        dimension_name: 维度名称
        cronbach_alpha: Cronbach's α系数
        n_items: 题目数量
        n_respondents: 受访者数量
        mean_score: 平均分
        std_dev: 标准差
        item_statistics: 题目统计信息
        alpha_if_deleted: 删除各题后的α值
    """
    dimension_name: str
    cronbach_alpha: float
    n_items: int
    n_respondents: int
    mean_score: float
    std_dev: float
    item_statistics: List[Dict[str, Any]]
    alpha_if_deleted: Dict[str, float]


class ReliabilityValidator:
    """信效度验证器

    基于多个受访者的答案数据，计算Cronbach's α等信度指标。
    """

    def __init__(self, schema: QuestionnaireSchema):
        """初始化验证器

        Args:
            schema: 问卷Schema
        """
        self.schema = schema

    def validate(
        self,
        answers_list: List[Dict[str, Any]],
        dimension_name: Optional[str] = None
    ) -> ReliabilityResult:
        """验证信度

        Args:
            answers_list: 多个受访者的答案列表
                         格式: [{'q1': 4, 'q2': 2, ...}, {'q1': 5, 'q2': 1, ...}, ...]
            dimension_name: 维度名称（可选），如果为None则计算所有量表题的信度

        Returns:
            ReliabilityResult对象
        """
        # 1. 提取维度的题目
        questions = self._get_dimension_questions(dimension_name)

        if len(questions) < 2:
            raise ValueError(f"维度 '{dimension_name}' 至少需要2个题目才能计算信度")

        # 2. 构建答案矩阵
        response_matrix, valid_questions = self._build_response_matrix(
            answers_list, questions
        )

        if len(answers_list) < 2:
            raise ValueError(f"至少需要2个受访者的答案才能计算信度")

        # 3. 反向计分
        processed_matrix = self._reverse_score_items(response_matrix, valid_questions)

        # 4. 计算Cronbach's α
        alpha = self._calculate_cronbach_alpha(processed_matrix)

        # 5. 计算题目统计
        item_stats = self._calculate_item_statistics(processed_matrix, valid_questions)

        # 6. 计算Alpha if Item Deleted
        alpha_if_deleted = self._calculate_alpha_if_deleted(
            processed_matrix, valid_questions
        )

        # 7. 计算总分统计
        total_scores = np.sum(processed_matrix, axis=1)
        mean_score = float(np.mean(total_scores))
        std_dev = float(np.std(total_scores, ddof=1))

        result = ReliabilityResult(
            dimension_name=dimension_name or "整体",
            cronbach_alpha=alpha,
            n_items=len(valid_questions),
            n_respondents=len(answers_list),
            mean_score=mean_score,
            std_dev=std_dev,
            item_statistics=item_stats,
            alpha_if_deleted=alpha_if_deleted
        )

        return result

    def validate_all_dimensions(
        self,
        answers_list: List[Dict[str, Any]]
    ) -> Dict[str, ReliabilityResult]:
        """验证所有维度的信度

        Args:
            answers_list: 多个受访者的答案列表

        Returns:
            维度名称到ReliabilityResult的映射
        """
        results = {}

        # 获取所有维度
        dimensions = self._get_all_dimensions()

        for dim_name in dimensions:
            try:
                result = self.validate(answers_list, dim_name)
                results[dim_name] = result
            except ValueError as e:
                # 如果某个维度题目不足，跳过
                print(f"警告: 跳过维度 '{dim_name}': {e}")
                continue

        return results

    def _get_dimension_questions(
        self,
        dimension_name: Optional[str]
    ) -> List[Question]:
        """获取指定维度的量表题

        Args:
            dimension_name: 维度名称，None表示所有量表题

        Returns:
            Question列表
        """
        scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX]
        scale_questions = [q for q in self.schema.questions if q.type in scale_types]

        if dimension_name is None:
            return scale_questions

        # 从schema.metadata['dimensions']中查找
        dimensions_mapping = self.schema.metadata.get('dimensions', {})

        if dimension_name in dimensions_mapping:
            question_ids = dimensions_mapping[dimension_name]
            return [q for q in scale_questions if q.id in question_ids]

        # 如果没有维度映射，根据question.metadata['dimension']过滤
        return [q for q in scale_questions
                if q.metadata.get('dimension') == dimension_name]

    def _get_all_dimensions(self) -> List[str]:
        """获取所有维度名称

        Returns:
            维度名称列表
        """
        dimensions_mapping = self.schema.metadata.get('dimensions', {})

        if dimensions_mapping:
            return list(dimensions_mapping.keys())

        # 如果没有维度映射，从题目metadata中提取
        dimensions = set()
        scale_types = [QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX]

        for q in self.schema.questions:
            if q.type in scale_types and 'dimension' in q.metadata:
                dim = q.metadata['dimension']
                if dim:
                    dimensions.add(dim)

        return list(dimensions)

    def _build_response_matrix(
        self,
        answers_list: List[Dict[str, Any]],
        questions: List[Question]
    ) -> Tuple[np.ndarray, List[Question]]:
        """构建答案矩阵

        Args:
            answers_list: 答案列表
            questions: 题目列表

        Returns:
            (response_matrix, valid_questions)
            - response_matrix: numpy数组，shape=(n_respondents, n_items)
            - valid_questions: 有效题目列表（排除了全部缺失的题目）
        """
        matrix = []

        for answers in answers_list:
            row = []
            for q in questions:
                answer = answers.get(q.id)

                # 跳过None和非数字答案
                if answer is None:
                    row.append(np.nan)
                else:
                    try:
                        # 尝试转换为数字
                        if isinstance(answer, str):
                            row.append(float(answer))
                        else:
                            row.append(float(answer))
                    except (ValueError, TypeError):
                        row.append(np.nan)

            matrix.append(row)

        # 转换为numpy数组
        matrix = np.array(matrix)

        # 删除全是NaN的列（题目）
        valid_cols = ~np.all(np.isnan(matrix), axis=0)
        matrix = matrix[:, valid_cols]
        valid_questions = [q for i, q in enumerate(questions) if valid_cols[i]]

        # 删除包含NaN的行（受访者）
        valid_rows = ~np.any(np.isnan(matrix), axis=1)
        matrix = matrix[valid_rows, :]

        return matrix, valid_questions

    def _reverse_score_items(
        self,
        matrix: np.ndarray,
        questions: List[Question]
    ) -> np.ndarray:
        """对反向题进行反向计分

        Args:
            matrix: 答案矩阵
            questions: 题目列表

        Returns:
            处理后的矩阵
        """
        processed = matrix.copy()

        for i, q in enumerate(questions):
            if q.metadata.get('is_reverse', False):
                # 获取量表范围
                scale_min, scale_max = self._get_scale_range(q)

                # 反向计分: reversed = (min + max) - original
                processed[:, i] = (scale_min + scale_max) - processed[:, i]

        return processed

    def _get_scale_range(self, question: Question) -> Tuple[int, int]:
        """获取题目的量表范围

        Args:
            question: 题目对象

        Returns:
            (scale_min, scale_max)
        """
        if question.type == QuestionType.NPS:
            return (0, 10)
        elif question.type in [QuestionType.RATING, QuestionType.MATRIX]:
            if question.options:
                # Try to get range from options
                try:
                    if isinstance(question.options[0], dict):
                        # Extract values from {value, label} dicts
                        int_options = [int(opt['value']) for opt in question.options]
                        return (min(int_options), max(int_options))
                    elif isinstance(question.options[0], int):
                        return (min(question.options), max(question.options))
                    elif isinstance(question.options[0], str):
                        int_options = [int(opt) for opt in question.options]
                        return (min(int_options), max(int_options))
                except (ValueError, TypeError, KeyError):
                    pass

            # Default 1-5
            return (1, 5)
        else:
            return (1, 5)

    def _calculate_cronbach_alpha(self, matrix: np.ndarray) -> float:
        """计算Cronbach's α

        Args:
            matrix: 答案矩阵 (n_respondents, n_items)

        Returns:
            Cronbach's α值
        """
        n_items = matrix.shape[1]

        if n_items < 2:
            return 0.0

        # 计算每题的方差
        item_variances = np.var(matrix, axis=0, ddof=1)
        sum_item_var = np.sum(item_variances)

        # 计算总分的方差
        total_scores = np.sum(matrix, axis=1)
        total_var = np.var(total_scores, ddof=1)

        # 避免除以0
        if total_var == 0 or np.isnan(total_var):
            return 0.0

        # Cronbach's α公式
        alpha = (n_items / (n_items - 1)) * (1 - sum_item_var / total_var)

        return float(alpha)

    def _calculate_item_statistics(
        self,
        matrix: np.ndarray,
        questions: List[Question]
    ) -> List[Dict[str, Any]]:
        """计算题目统计信息

        包括：
        - 平均分
        - 标准差
        - Item-Total Correlation（题目-总分相关性）

        Args:
            matrix: 答案矩阵
            questions: 题目列表

        Returns:
            题目统计列表
        """
        stats = []
        total_scores = np.sum(matrix, axis=1)

        for i, q in enumerate(questions):
            item_scores = matrix[:, i]

            # 计算Corrected Item-Total Correlation
            # 从总分中减去当前题目的分数
            corrected_total = total_scores - item_scores

            # 计算相关系数
            correlation = np.corrcoef(item_scores, corrected_total)[0, 1]

            stats.append({
                'question_id': q.id,
                'question_label': q.label[:50] + "..." if len(q.label) > 50 else q.label,
                'is_reverse': q.metadata.get('is_reverse', False),
                'mean': float(np.mean(item_scores)),
                'std_dev': float(np.std(item_scores, ddof=1)),
                'item_total_correlation': float(correlation) if not np.isnan(correlation) else 0.0,
            })

        return stats

    def _calculate_alpha_if_deleted(
        self,
        matrix: np.ndarray,
        questions: List[Question]
    ) -> Dict[str, float]:
        """计算删除某题后的α值

        Args:
            matrix: 答案矩阵
            questions: 题目列表

        Returns:
            question_id -> alpha_if_deleted的映射
        """
        result = {}

        for i, q in enumerate(questions):
            # 删除第i列
            reduced_matrix = np.delete(matrix, i, axis=1)

            if reduced_matrix.shape[1] < 2:
                # 剩余题目不足2题
                result[q.id] = 0.0
            else:
                alpha = self._calculate_cronbach_alpha(reduced_matrix)
                result[q.id] = alpha

        return result

    def generate_report(self, result: ReliabilityResult) -> str:
        """生成信度分析报告

        Args:
            result: 信度分析结果

        Returns:
            格式化的报告文本
        """
        report_lines = []

        # 标题
        report_lines.append("=" * 100)
        report_lines.append(f"信度分析报告 - {result.dimension_name}".center(100))
        report_lines.append("=" * 100)
        report_lines.append("")

        # 总体信度
        report_lines.append("【总体信度】")
        report_lines.append("-" * 100)
        report_lines.append(f"  Cronbach's α: {result.cronbach_alpha:.4f}  {self._interpret_alpha(result.cronbach_alpha)}")
        report_lines.append(f"  题目数量: {result.n_items}")
        report_lines.append(f"  受访者数量: {result.n_respondents}")
        report_lines.append(f"  总分均值: {result.mean_score:.2f}")
        report_lines.append(f"  总分标准差: {result.std_dev:.2f}")
        report_lines.append("")

        # 题目统计
        report_lines.append("【题目统计】")
        report_lines.append("-" * 100)
        report_lines.append(f"{'题目ID':<12} {'反向':<6} {'均值':<10} {'标准差':<10} {'题总相关':<12} {'删除后α':<12} {'题目'}")
        report_lines.append("-" * 100)

        for stat in result.item_statistics:
            q_id = stat['question_id']
            is_reverse = "🔴" if stat['is_reverse'] else "🟢"
            mean = stat['mean']
            std = stat['std_dev']
            corr = stat['item_total_correlation']
            alpha_del = result.alpha_if_deleted.get(q_id, 0.0)
            label = stat['question_label']

            report_lines.append(
                f"{q_id:<12} {is_reverse:<6} {mean:<10.2f} {std:<10.2f} "
                f"{corr:<12.3f} {alpha_del:<12.4f} {label}"
            )

        report_lines.append("")

        # 建议
        report_lines.append("【分析建议】")
        report_lines.append("-" * 100)

        if result.cronbach_alpha >= 0.9:
            report_lines.append("  ✅ 信度优秀（α ≥ 0.9），适合发表顶级期刊")
        elif result.cronbach_alpha >= 0.8:
            report_lines.append("  ✅ 信度良好（α ≥ 0.8），适合硕士/博士论文")
        elif result.cronbach_alpha >= 0.7:
            report_lines.append("  ⚠️  信度可接受（α ≥ 0.7），建议优化量表")
        else:
            report_lines.append("  ❌ 信度不足（α < 0.7），需要重新设计量表")

        # 检查问题题目
        problem_items = [
            stat for stat in result.item_statistics
            if stat['item_total_correlation'] < 0.3
        ]

        if problem_items:
            report_lines.append("")
            report_lines.append("  问题题目（题总相关性 < 0.3）：")
            for stat in problem_items:
                report_lines.append(f"    - {stat['question_id']}: {stat['question_label']}")
                report_lines.append(f"      建议：考虑删除或修改该题，删除后α = {result.alpha_if_deleted.get(stat['question_id'], 0.0):.4f}")

        report_lines.append("")

        return "\n".join(report_lines)

    def _interpret_alpha(self, alpha: float) -> str:
        """解释α值

        Args:
            alpha: Cronbach's α值

        Returns:
            解释文本
        """
        if alpha >= 0.9:
            return "✅ 优秀"
        elif alpha >= 0.8:
            return "✅ 良好"
        elif alpha >= 0.7:
            return "⚠️  可接受"
        elif alpha >= 0.6:
            return "⚠️  勉强可接受"
        else:
            return "❌ 不可接受"
