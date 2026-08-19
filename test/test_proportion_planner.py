"""Tests for strict proportional answer planning."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from api.models import AnalyzeRequest, SubmitRequest
from api.routers.questionnaire import _question_display_metadata, _ratio_metadata
from core.proportion_planner import (
    ProportionConfigError,
    build_proportion_plan,
    summarize_plan,
)
from core.schema import (
    AnswerStrategy,
    Question,
    QuestionnaireSchema,
    QuestionType,
    SelectorConfig,
)
from db.models import QuestionnaireTask, TaskProportionAnswerPlan


def question(question_id, question_type, options, *, required=True, params=None, metadata=None):
    return Question(
        id=question_id,
        type=question_type,
        label=question_id,
        options=[{"value": value, "label": str(value)} for value in options],
        selector=SelectorConfig(template=""),
        strategy=AnswerStrategy(type="random_sample", params=params or {}),
        required=required,
        metadata=metadata or {},
    )


class ProportionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.radio = question("q1", QuestionType.RADIO, [1, 2])
        self.checkbox = question(
            "q2", QuestionType.CHECKBOX, [1, 2, 3], params={"min": 1, "max": 2}
        )
        self.matrix = question(
            "q7_0", QuestionType.MATRIX, [1, 2, 3], metadata={"base_id": "q7"}
        )
        self.schema = QuestionnaireSchema(
            url="https://example.test",
            activity_id="test",
            platform="test",
            questions=[self.radio, self.checkbox, self.matrix],
        )

    def test_radio_60_40_produces_exact_counts_for_100(self):
        plans = build_proportion_plan(
            self.schema,
            {"questions": [{"question_id": "q1", "options": [
                {"value": 1, "percentage": 60}, {"value": 2, "percentage": 40}
            ]}]},
            100,
            seed=7,
        )
        self.assertEqual(summarize_plan(plans)["q1"], {"1": 60, "2": 40})

    def test_largest_remainder_produces_total_for_seven(self):
        three = question("q3", QuestionType.RADIO, [1, 2, 3])
        schema = QuestionnaireSchema("", "", "", [three])
        plans = build_proportion_plan(schema, {"questions": [{"question_id": "q3", "options": [
            {"value": 1, "percentage": 50},
            {"value": 2, "percentage": 30},
            {"value": 3, "percentage": 20},
        ]}]}, 7)
        self.assertEqual(summarize_plan(plans)["q3"], {"1": 4, "2": 2, "3": 1})

    def test_checkbox_quotas_and_row_limits_are_exact(self):
        plans = build_proportion_plan(self.schema, {"questions": [{"question_id": "q2", "options": [
            {"value": 1, "percentage": 80},
            {"value": 2, "percentage": 60},
            {"value": 3, "percentage": 40},
        ]}]}, 10, seed=2)
        self.assertEqual(summarize_plan(plans)["q2"], {"1": 8, "2": 6, "3": 4})
        self.assertTrue(all(1 <= len(plan["q2"]) <= 2 for plan in plans))

    def test_checkbox_impossible_capacity_is_rejected(self):
        with self.assertRaises(ProportionConfigError):
            build_proportion_plan(self.schema, {"questions": [{"question_id": "q2", "options": [
                {"value": 1, "percentage": 100},
                {"value": 2, "percentage": 100},
                {"value": 3, "percentage": 100},
            ]}]}, 10)

    def test_wrong_option_count_and_sum_are_rejected(self):
        with self.assertRaises(ProportionConfigError):
            build_proportion_plan(self.schema, {"questions": [{"question_id": "q1", "options": [
                {"value": 1, "percentage": 100}
            ]}]}, 10)
        with self.assertRaises(ProportionConfigError):
            build_proportion_plan(self.schema, {"questions": [{"question_id": "q1", "options": [
                {"value": 1, "percentage": 50}, {"value": 2, "percentage": 40}
            ]}]}, 10)

    def test_fill_in_checkbox_option_must_be_zero(self):
        checkbox = question(
            "q4", QuestionType.CHECKBOX, [1, 2, 3],
            params={"min": 1, "max": 2}, metadata={"other_option_value": 3}
        )
        schema = QuestionnaireSchema("", "", "", [checkbox])
        with self.assertRaises(ProportionConfigError):
            build_proportion_plan(schema, {"questions": [{"question_id": "q4", "options": [
                {"value": 1, "percentage": 80},
                {"value": 2, "percentage": 60},
                {"value": 3, "percentage": 20},
            ]}]}, 10)

    def test_matrix_row_metadata_is_exposed(self):
        metadata = _ratio_metadata(self.matrix)
        self.assertTrue(metadata["ratio_eligible"])
        self.assertEqual(metadata["parent_question_id"], "q7")
        matrix2 = question("q7_1", QuestionType.MATRIX, [1, 2, 3], metadata={"base_id": "q7"})
        display = _question_display_metadata([self.radio, self.matrix, matrix2])
        self.assertEqual(display["q1"]["ratio_display_key"], "1")
        self.assertEqual(display["q7_0"]["ratio_display_key"], "2.1")
        self.assertEqual(display["q7_1"]["ratio_display_key"], "2.2")


class ProportionApiAndDatabaseTests(unittest.TestCase):
    def test_structure_analysis_mode_and_proportional_submit_models(self):
        analyze = AnalyzeRequest(url="https://example.com", analysis_mode="proportional", use_ai=True)
        self.assertEqual(analyze.analysis_mode, "proportional")
        request = SubmitRequest(
            task_id="task-id", count=10, mode="proportional",
            proportion_config={"questions": [{"question_id": "q1", "options": [
                {"value": 1, "percentage": 60}, {"value": 2, "percentage": 40}
            ]}]},
        )
        self.assertEqual(request.mode, "proportional")

    def test_proportional_mode_requires_config(self):
        with self.assertRaises(ValidationError):
            SubmitRequest(task_id="task-id", count=10, mode="proportional")

    def test_database_columns_and_plan_table_exist(self):
        for name in (
            "proportion_config", "proportion_plan_status", "proportion_plan_count",
            "proportion_plan_seed", "proportion_max_submit_attempts",
        ):
            self.assertIn(name, QuestionnaireTask.__table__.columns)
        self.assertIn("submit_index", TaskProportionAnswerPlan.__table__.columns)
        self.assertIn("answers", TaskProportionAnswerPlan.__table__.columns)


if __name__ == "__main__":
    unittest.main()
