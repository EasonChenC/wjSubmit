"""Regression tests for textarea default answer generation."""

import unittest

from core.dynamic_answer_generator import DynamicAnswerGenerator
from core.schema import (
    AnswerStrategy,
    Question,
    QuestionnaireSchema,
    QuestionType,
    SelectorConfig,
)


class TextareaAnswerStrategyTests(unittest.TestCase):
    def setUp(self):
        self.question = Question(
            id="q1",
            type=QuestionType.TEXTAREA,
            label="请填写其他意见",
            options=[],
            selector=SelectorConfig(template="textarea#q1"),
            strategy=AnswerStrategy(type="text_pool", params={"pool": []}),
            required=True,
        )
        self.generator = DynamicAnswerGenerator(
            QuestionnaireSchema(
                url="https://example.test",
                activity_id="test",
                platform="test",
                questions=[self.question],
            )
        )

    def test_empty_pool_defaults_to_none_text(self):
        answer = self.generator._generate_textarea_answer(
            self.question, self.question.strategy
        )
        self.assertEqual(answer, "无")

    def test_configured_pool_still_takes_precedence(self):
        strategy = AnswerStrategy(type="text_pool", params={"pool": ["自定义回答"]})
        answer = self.generator._generate_textarea_answer(self.question, strategy)
        self.assertEqual(answer, "自定义回答")


if __name__ == "__main__":
    unittest.main()
