"""Regression tests for checkbox minvalue/maxvalue analysis."""

from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

from core.rule_based_analyzer import RuleBasedAnalyzer
from core.schema import QuestionType


class CheckboxSelectionLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = RuleBasedAnalyzer()
        self.options = [
            {"value": value, "label": str(value)} for value in range(1, 14)
        ]

    def strategy_params(self, attributes: str) -> dict:
        div = BeautifulSoup(
            f'<div type="4" {attributes}></div>', "html.parser"
        ).div
        strategy = self.analyzer._generate_strategy(
            QuestionType.CHECKBOX, self.options, div=div
        )
        return strategy.params

    def test_minimum_above_default_maximum_normalizes_maximum(self) -> None:
        self.assertEqual(
            self.strategy_params('minvalue="5"'),
            {"min": 5, "max": 5},
        )

    def test_explicit_maximum_is_preserved(self) -> None:
        self.assertEqual(
            self.strategy_params('minvalue="2" maxvalue="3"'),
            {"min": 2, "max": 3},
        )

    def test_normal_minimum_keeps_default_maximum(self) -> None:
        self.assertEqual(
            self.strategy_params('minvalue="2"'),
            {"min": 2, "max": 4},
        )


if __name__ == "__main__":
    unittest.main()
