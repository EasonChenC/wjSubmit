"""AI generation and validation for deterministic text-question answer pools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

from .client import AIClient


class TextAnswerPoolError(ValueError):
    """Raised when an AI response cannot form a complete answer batch."""


def _load_prompt() -> str:
    path = Path(__file__).parent.parent / "prompt" / "textarea_answer_generation.txt"
    return path.read_text(encoding="utf-8")


def _extract_json(response: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating an accidental Markdown fence."""
    if not response or not response.strip():
        raise TextAnswerPoolError("AI returned an empty response")

    text = response.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    first = text.find("{")
    last = text.rfind("}")
    if first < 0 or last < first:
        raise TextAnswerPoolError("AI response does not contain a JSON object")

    try:
        value = json.loads(text[first:last + 1])
    except json.JSONDecodeError as exc:
        raise TextAnswerPoolError(f"AI response is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise TextAnswerPoolError("AI response root must be an object")
    return value


def validate_answer_batch(
    response: str,
    submission_count: int,
    question_ids: Iterable[str],
) -> list[dict[str, str]]:
    """Validate the strict response schema and return answers in index order."""
    expected_ids = list(question_ids)
    expected_set = set(expected_ids)
    if len(expected_set) != len(expected_ids):
        raise TextAnswerPoolError("Text question IDs must be unique")

    payload = _extract_json(response)
    responses = payload.get("responses")
    if set(payload) != {"responses"} or not isinstance(responses, list):
        raise TextAnswerPoolError("AI response must contain only a responses array")
    if len(responses) != submission_count:
        raise TextAnswerPoolError(
            f"Expected {submission_count} responses, got {len(responses)}"
        )

    by_index: dict[int, dict[str, str]] = {}
    for item in responses:
        if not isinstance(item, dict) or set(item) != {"submission_index", "answers"}:
            raise TextAnswerPoolError(
                "Each response must contain only submission_index and answers"
            )
        index = item["submission_index"]
        answers = item["answers"]
        if isinstance(index, bool) or not isinstance(index, int):
            raise TextAnswerPoolError("submission_index must be an integer")
        if index in by_index:
            raise TextAnswerPoolError(f"Duplicate submission_index: {index}")
        if not isinstance(answers, dict) or set(answers) != expected_set:
            raise TextAnswerPoolError(
                f"Answer keys for submission {index} do not match text question IDs"
            )

        normalized: dict[str, str] = {}
        for question_id in expected_ids:
            answer = answers[question_id]
            if not isinstance(answer, str) or not answer.strip():
                raise TextAnswerPoolError(
                    f"Answer for {question_id} in submission {index} must be non-empty"
                )
            normalized[question_id] = answer.strip()
        by_index[index] = normalized

    expected_indexes = set(range(1, submission_count + 1))
    if set(by_index) != expected_indexes:
        raise TextAnswerPoolError("submission_index must be continuous from 1")
    return [by_index[index] for index in range(1, submission_count + 1)]


class TextareaAnswerPoolGenerator:
    """Generate one validated batch for all supplied single/multiline text questions."""

    def __init__(self, client: AIClient, max_attempts: int = 3):
        self.client = client
        self.max_attempts = max_attempts
        self.prompt_template = _load_prompt()

    async def generate_batch(
        self,
        questions: list[dict[str, str]],
        submission_count: int,
    ) -> list[dict[str, str]]:
        if submission_count < 1:
            return []
        question_ids = [question["id"] for question in questions]
        prompt = self.prompt_template.format(
            submission_count=submission_count,
            questions_json=json.dumps(questions, ensure_ascii=False, indent=2),
        )

        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = await self.client.chat(
                    [{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=min(
                        16000,
                        max(4096, submission_count * max(1, len(questions)) * 160),
                    ),
                )
                return validate_answer_batch(response, submission_count, question_ids)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    await asyncio.sleep(min(attempt, 2))

        raise TextAnswerPoolError(
            f"Failed to generate a valid textarea answer batch after "
            f"{self.max_attempts} attempts: {last_error}"
        ) from last_error
