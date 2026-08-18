"""Tests for AI-generated deterministic textarea answer pools."""

from __future__ import annotations

import asyncio
import json
import unittest

from ai.text_answer_pool import (
    TextAnswerPoolError,
    TextareaAnswerPoolGenerator,
    validate_answer_batch,
)
from api.models import SubmitRequest
from api.routers.questionnaire import (
    is_ai_text_question,
    text_overrides_for_submission,
)
from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.schema import (
    AnswerStrategy,
    Question,
    QuestionnaireSchema,
    QuestionType,
    SelectorConfig,
)
from db.models import QuestionnaireTask, TaskTextAnswerPool


class FakeAIClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


def make_response(count: int) -> str:
    return json.dumps(
        {
            "responses": [
                {
                    "submission_index": index,
                    "answers": {
                        "q12": f"第{index}份对q12的回答",
                        "q18": f"第{index}份对q18的回答",
                    },
                }
                for index in range(1, count + 1)
            ]
        },
        ensure_ascii=False,
    )


class AnswerBatchValidationTests(unittest.TestCase):
    def test_valid_json_is_returned_in_submission_order(self):
        answers = validate_answer_batch(make_response(2), 2, ["q12", "q18"])
        self.assertEqual(answers[0]["q12"], "第1份对q12的回答")
        self.assertEqual(answers[1]["q18"], "第2份对q18的回答")

    def test_fenced_json_is_tolerated(self):
        answers = validate_answer_batch(
            f"```json\n{make_response(1)}\n```", 1, ["q12", "q18"]
        )
        self.assertEqual(len(answers), 1)

    def test_missing_question_id_is_rejected(self):
        payload = json.loads(make_response(1))
        del payload["responses"][0]["answers"]["q18"]
        with self.assertRaises(TextAnswerPoolError):
            validate_answer_batch(json.dumps(payload), 1, ["q12", "q18"])

    def test_non_continuous_indexes_are_rejected(self):
        payload = json.loads(make_response(2))
        payload["responses"][1]["submission_index"] = 3
        with self.assertRaises(TextAnswerPoolError):
            validate_answer_batch(json.dumps(payload), 2, ["q12", "q18"])

    def test_prompt_generator_uses_only_supplied_question_data(self):
        client = FakeAIClient(make_response(2))
        generator = TextareaAnswerPoolGenerator(client, max_attempts=1)
        result = asyncio.run(
            generator.generate_batch(
                [
                    {"id": "q12", "label": "请说明原因"},
                    {"id": "q18", "label": "请提出建议"},
                ],
                2,
            )
        )
        prompt = client.calls[0][0][0]["content"]
        self.assertIn("请说明原因", prompt)
        self.assertIn("需要生成的问卷份数：2", prompt)
        self.assertEqual(len(result), 2)


class DeterministicAssignmentTests(unittest.TestCase):
    def setUp(self):
        question = Question(
            id="q12",
            type=QuestionType.TEXTAREA,
            label="建议",
            options=[],
            selector=SelectorConfig(template="textarea#q12"),
            strategy=AnswerStrategy(type="text_pool", params={"pool": ["随机池"]}),
            required=True,
        )
        self.generator = DynamicAnswerGenerator(
            QuestionnaireSchema(
                url="https://example.test",
                activity_id="test",
                platform="test",
                questions=[question],
            )
        )

    def test_submission_index_selects_exact_pool_offset(self):
        pools = {"q12": ["第一份", "第二份", "第三份"]}
        override = text_overrides_for_submission(pools, 2)
        answers = self.generator.generate_answers(override)
        self.assertEqual(answers["q12"], "第二份")

    def test_missing_pool_offset_fails_instead_of_random_fallback(self):
        with self.assertRaises(TextAnswerPoolError):
            text_overrides_for_submission({"q12": ["第一份"]}, 2)

    def test_single_line_and_multiline_questions_are_both_ai_eligible(self):
        single_line = self.generator.schema.questions[0]
        multiline = Question(
            id="q18",
            type=QuestionType.TEXTAREA,
            label="建议",
            options=[],
            selector=SelectorConfig(template="textarea#q18"),
            strategy=AnswerStrategy(type="text_pool", params={"pool": []}),
            required=True,
        )
        self.assertTrue(is_ai_text_question(single_line))
        self.assertTrue(is_ai_text_question(multiline))

    def test_single_line_ai_override_replaces_original_random_strategy(self):
        single_line = self.generator.schema.questions[0]
        single_line.type = QuestionType.TEXT
        single_line.strategy = AnswerStrategy(type="random_int", params={"min": 1, "max": 100})
        answers = self.generator.generate_answers({"q12": "25"})
        self.assertEqual(answers["q12"], "25")


class ApiAndDatabaseTests(unittest.TestCase):
    def test_submit_request_accepts_ai_text_config(self):
        request = SubmitRequest(
            task_id="task-id",
            count=100,
            mode="random",
            ai_text={"enabled": True, "batch_size": 20, "max_generation_attempts": 4},
        )
        self.assertTrue(request.ai_text.enabled)
        self.assertEqual(request.ai_text.batch_size, 20)

    def test_ai_text_database_columns_and_pool_table_exist(self):
        for name in (
            "ai_text_enabled",
            "ai_text_batch_size",
            "ai_text_status",
            "ai_text_generated_count",
            "ai_text_model",
            "ai_text_error",
        ):
            self.assertIn(name, QuestionnaireTask.__table__.columns)
        self.assertIn("question_id", TaskTextAnswerPool.__table__.columns)
        self.assertIn("answers", TaskTextAnswerPool.__table__.columns)


if __name__ == "__main__":
    unittest.main()
