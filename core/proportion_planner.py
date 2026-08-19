"""Deterministic task-level answer planning for proportional submission mode."""

from __future__ import annotations

import json
import math
import random
from decimal import Decimal
from typing import Any

from .schema import Question, QuestionnaireSchema, QuestionType


ELIGIBLE_TYPES = {
    QuestionType.RADIO,
    QuestionType.CHECKBOX,
    QuestionType.SELECT,
    QuestionType.MATRIX,
    QuestionType.RATING,
    QuestionType.NPS,
}


class ProportionConfigError(ValueError):
    """A proportional configuration is invalid or mathematically infeasible."""


def _option_value(option: Any) -> Any:
    return option.get("value") if isinstance(option, dict) else option


def _key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def largest_remainder_counts(percentages: list[Decimal], total: int) -> list[int]:
    """Convert percentages summing to 100 into exact integer quotas."""
    raw = [percentage * total / Decimal("100") for percentage in percentages]
    counts = [math.floor(value) for value in raw]
    remaining = total - sum(counts)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - counts[i], -i), reverse=True)
    for index in order[:remaining]:
        counts[index] += 1
    return counts


def independent_counts(percentages: list[Decimal], total: int) -> list[int]:
    """Round independent checkbox percentages to nearest integer quota."""
    counts: list[int] = []
    for percentage in percentages:
        raw = percentage * total / Decimal("100")
        # Decimal ROUND_HALF_UP without importing a context-specific rounding mode.
        counts.append(int(raw + Decimal("0.5")))
    return counts


def _selection_bounds(question: Question, option_count: int) -> tuple[int, int]:
    params = question.strategy.params or {}
    default_min = 1 if question.required else 0
    minimum = int(params.get("min", default_min))
    maximum = int(params.get("max", option_count))
    if question.required:
        minimum = max(1, minimum)
    minimum = max(0, min(minimum, option_count))
    maximum = max(minimum, min(maximum, option_count))
    return minimum, maximum


def _checkbox_assignments(
    counts: list[int],
    values: list[Any],
    submission_count: int,
    minimum: int,
    maximum: int,
    rng: random.Random,
) -> list[list[Any]]:
    """Build a binary assignment with exact column quotas and row bounds."""
    total_selections = sum(counts)
    if any(count < 0 or count > submission_count for count in counts):
        raise ProportionConfigError("Checkbox option quota is outside 0..submission_count")
    if total_selections < submission_count * minimum:
        raise ProportionConfigError(
            f"Checkbox ratios require {total_selections} selections, but at least "
            f"{submission_count * minimum} are required"
        )
    if total_selections > submission_count * maximum:
        raise ProportionConfigError(
            f"Checkbox ratios require {total_selections} selections, but at most "
            f"{submission_count * maximum} are allowed"
        )

    row_degrees = [minimum] * submission_count
    extra = total_selections - sum(row_degrees)
    row_order = list(range(submission_count))
    rng.shuffle(row_order)
    cursor = 0
    while extra:
        row = row_order[cursor % submission_count]
        cursor += 1
        if row_degrees[row] >= maximum:
            if all(degree >= maximum for degree in row_degrees):
                raise ProportionConfigError("Checkbox row capacity is insufficient")
            continue
        row_degrees[row] += 1
        extra -= 1

    # Dinic max-flow gives a complete feasibility decision for the bipartite
    # option-to-submission assignment instead of relying on a greedy heuristic.
    option_count = len(values)
    source = 0
    option_start = 1
    row_start = option_start + option_count
    sink = row_start + submission_count
    graph: list[list[list[int]]] = [[] for _ in range(sink + 1)]

    def add_edge(start: int, end: int, capacity: int) -> None:
        graph[start].append([end, capacity, len(graph[end])])
        graph[end].append([start, 0, len(graph[start]) - 1])

    for option_index, count in enumerate(counts):
        add_edge(source, option_start + option_index, count)
    row_indexes = list(range(submission_count))
    rng.shuffle(row_indexes)
    for option_index in range(option_count):
        for row in row_indexes:
            add_edge(option_start + option_index, row_start + row, 1)
    for row, degree in enumerate(row_degrees):
        add_edge(row_start + row, sink, degree)

    flow = 0
    while True:
        level = [-1] * len(graph)
        level[source] = 0
        queue = [source]
        for node in queue:
            for end, capacity, _ in graph[node]:
                if capacity and level[end] < 0:
                    level[end] = level[node] + 1
                    queue.append(end)
        if level[sink] < 0:
            break
        cursor = [0] * len(graph)

        def send(node: int, amount: int) -> int:
            if node == sink:
                return amount
            while cursor[node] < len(graph[node]):
                edge = graph[node][cursor[node]]
                end, capacity, reverse = edge
                if capacity and level[end] == level[node] + 1:
                    sent = send(end, min(amount, capacity))
                    if sent:
                        edge[1] -= sent
                        graph[end][reverse][1] += sent
                        return sent
                cursor[node] += 1
            return 0

        while True:
            sent = send(source, total_selections - flow)
            if not sent:
                break
            flow += sent

    if flow != total_selections:
        raise ProportionConfigError(
            "Checkbox ratios cannot be combined while satisfying per-response limits"
        )

    assignments: list[list[Any]] = [[] for _ in range(submission_count)]
    for option_index in range(option_count):
        node = option_start + option_index
        for end, capacity, _ in graph[node]:
            if row_start <= end < sink and capacity == 0:
                assignments[end - row_start].append(values[option_index])
    for answer in assignments:
        answer.sort(key=lambda value: values.index(value))
    return assignments


def _validate_question_config(question: Question, config: dict[str, Any]) -> tuple[list[Any], list[Decimal]]:
    if question.type not in ELIGIBLE_TYPES:
        raise ProportionConfigError(f"Question {question.id} does not support option ratios")
    configured_options = config.get("options")
    if not isinstance(configured_options, list):
        raise ProportionConfigError(f"Question {question.id} options must be an array")

    actual_values = [_option_value(option) for option in question.options]
    if len(configured_options) != len(actual_values):
        raise ProportionConfigError(
            f"Question {question.id} requires exactly {len(actual_values)} option ratios"
        )

    configured_map: dict[str, Decimal] = {}
    for item in configured_options:
        if not isinstance(item, dict) or "value" not in item or "percentage" not in item:
            raise ProportionConfigError(f"Question {question.id} has an invalid option ratio")
        key = _key(item["value"])
        if key in configured_map:
            raise ProportionConfigError(f"Question {question.id} contains a duplicate option")
        try:
            percentage = Decimal(str(item["percentage"]))
        except Exception as exc:
            raise ProportionConfigError(f"Question {question.id} percentage must be numeric") from exc
        if percentage < 0 or percentage > 100:
            raise ProportionConfigError(f"Question {question.id} percentage must be within 0..100")
        configured_map[key] = percentage

    if set(configured_map) != {_key(value) for value in actual_values}:
        raise ProportionConfigError(f"Question {question.id} option values do not match analyzed schema")
    percentages = [configured_map[_key(value)] for value in actual_values]

    expected_sum = sum(percentages, Decimal("0"))
    if question.type == QuestionType.CHECKBOX:
        if expected_sum <= 100:
            raise ProportionConfigError(f"Checkbox question {question.id} ratios must sum to more than 100")
        other_value = question.metadata.get("other_option_value")
        if other_value is not None:
            other_index = next((i for i, value in enumerate(actual_values) if _key(value) == _key(other_value)), None)
            if other_index is not None and percentages[other_index] != 0:
                raise ProportionConfigError(f"Fill-in option of question {question.id} must have ratio 0")
    elif expected_sum != 100:
        raise ProportionConfigError(f"Question {question.id} ratios must sum to exactly 100")
    return actual_values, percentages


def build_proportion_plan(
    schema: QuestionnaireSchema,
    proportion_config: dict[str, Any],
    submission_count: int,
    *,
    seed: int = 0,
) -> list[dict[str, Any]]:
    """Validate configuration and build one deterministic override map per submission."""
    if submission_count < 1:
        raise ProportionConfigError("submission_count must be positive")
    question_configs = proportion_config.get("questions")
    if not isinstance(question_configs, list) or not question_configs:
        raise ProportionConfigError("At least one question ratio configuration is required")

    schema_map = {question.id: question for question in schema.questions}
    seen: set[str] = set()
    plans: list[dict[str, Any]] = [{} for _ in range(submission_count)]
    rng = random.Random(seed)

    for config in question_configs:
        if not isinstance(config, dict) or not config.get("enabled", True):
            continue
        question_id = config.get("question_id")
        if not isinstance(question_id, str) or question_id not in schema_map:
            raise ProportionConfigError(f"Unknown proportional question: {question_id}")
        if question_id in seen:
            raise ProportionConfigError(f"Duplicate proportional question: {question_id}")
        seen.add(question_id)

        question = schema_map[question_id]
        values, percentages = _validate_question_config(question, config)
        if question.type == QuestionType.CHECKBOX:
            counts = independent_counts(percentages, submission_count)
            minimum, maximum = _selection_bounds(question, len(values))
            assignments = _checkbox_assignments(
                counts, values, submission_count, minimum, maximum, rng
            )
            for index, answer in enumerate(assignments):
                plans[index][question_id] = answer
        else:
            counts = largest_remainder_counts(percentages, submission_count)
            assignments = [value for value, count in zip(values, counts) for _ in range(count)]
            rng.shuffle(assignments)
            for index, answer in enumerate(assignments):
                plans[index][question_id] = answer

    if not seen:
        raise ProportionConfigError("At least one enabled question ratio configuration is required")
    return plans


def summarize_plan(plans: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Return exact planned option counts for verification and API tests."""
    summary: dict[str, dict[str, int]] = {}
    for plan in plans:
        for question_id, answer in plan.items():
            values = answer if isinstance(answer, list) else [answer]
            question_summary = summary.setdefault(question_id, {})
            for value in values:
                key = _key(value)
                question_summary[key] = question_summary.get(key, 0) + 1
    return summary
