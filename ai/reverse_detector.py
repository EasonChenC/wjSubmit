"""AI-based reverse item detection with scale question identification"""

import json
from pathlib import Path
from typing import Optional

from core.schema import QuestionnaireSchema, QuestionType
from .client import AIClient


def _load_prompt(prompt_name: str) -> str:
    """Load prompt template from prompt directory"""
    prompt_path = Path(__file__).parent.parent / "prompt" / f"{prompt_name}.txt"
    return prompt_path.read_text(encoding='utf-8')


def _normalize_options(options):
    """
    Normalize options to {value, label} format.

    Handles: integers, strings, dicts with value/label.
    """
    if not options:
        return []

    first = options[0]

    if isinstance(first, dict):
        # Already in dict format
        return [
            {"value": str(opt.get("value", opt.get("rowid", ""))), "label": opt.get("label")}
            for opt in options
        ]
    elif isinstance(first, (int, str)):
        # Convert scalar values to dict format
        return [{"value": str(v)} for v in options]
    else:
        return []


async def override_schema_with_ai_detection(schema: QuestionnaireSchema,
                                           ai_client: AIClient) -> None:
    """
    Override reverse item detection with AI results.

    AI analyzes all scale-type questions (rating, nps, matrix, radio) to:
    1. Identify which radio questions are scale questions
    2. Classify each scale question as forward or reverse
    3. Identify positive/negative/neutral values for each scale question

    Falls back to keyword detection if AI fails.

    Args:
        schema: Questionnaire schema to update
        ai_client: Initialized AI client
    """
    # Extract scale questions + potential radio scale questions
    scale_types = {QuestionType.RATING, QuestionType.NPS, QuestionType.MATRIX}
    radio_type = {QuestionType.RADIO}

    scale_questions = [q for q in schema.questions if q.type in scale_types]
    radio_questions = [q for q in schema.questions if q.type in radio_type]

    # Combine for AI analysis
    all_analysis_questions = scale_questions + radio_questions

    if not all_analysis_questions:
        return

    try:
        # Prepare prompt and questions data
        prompt_template = _load_prompt("reverse_item_detection")

        # Format questions for AI
        questions_data = [
            {
                "id": q.id,
                "type": q.type.value,
                "label": q.label,
                "options": _normalize_options(q.options)
            }
            for q in all_analysis_questions
        ]

        user_message = prompt_template.format(
            questions_json=json.dumps(questions_data, ensure_ascii=False, indent=2)
        )

        messages = [{"role": "user", "content": user_message}]

        # Get AI response
        response_text = await ai_client.chat(messages, temperature=0.1)

        # Parse AI response
        result = _parse_ai_response(response_text)

        if result:
            _apply_ai_results(schema, all_analysis_questions, result)

    except Exception as e:
        # Fallback: keep keyword detection results and mark AI as failed
        schema.metadata['ai_detection_error'] = str(e)


def _apply_ai_results(schema: QuestionnaireSchema, questions: list, ai_result: dict) -> None:
    """Apply AI detection results to schema"""

    scale_items = ai_result.get('scale_items', [])
    non_scale_ids = set(ai_result.get('non_scale_ids', []))

    # Build lookup for AI results
    ai_scale_map = {item['id']: item for item in scale_items}

    reverse_item_ids = []

    for question in questions:
        if question.id in ai_scale_map:
            # AI identified this as a scale question
            ai_item = ai_scale_map[question.id]

            question.metadata['is_scale'] = True
            question.metadata['is_reverse'] = ai_item.get('is_reverse', False)
            question.metadata['detection_method'] = 'ai'
            question.metadata['positive_values'] = ai_item.get('positive_values', [])
            question.metadata['negative_values'] = ai_item.get('negative_values', [])
            question.metadata['neutral_values'] = ai_item.get('neutral_values', [])
            question.metadata['reverse_keywords'] = []

            if ai_item.get('is_reverse'):
                reverse_item_ids.append(question.id)

        elif question.id in non_scale_ids:
            # AI identified this as NOT a scale question
            question.metadata['is_scale'] = False
            question.metadata['detection_method'] = 'ai'
        # else: no decision from AI, keep existing metadata

    # Update schema metadata
    schema.metadata['reverse_items'] = reverse_item_ids
    schema.metadata['ai_detection'] = True
    schema.metadata['scale_items_with_direction'] = [
        item for item in scale_items
    ]


def _parse_ai_response(response: str) -> Optional[dict]:
    """Extract JSON from AI response (handles markdown code blocks)"""
    response = response.strip()

    # Try to extract JSON from markdown code block
    if '```json' in response:
        start = response.index('```json') + 7
        end = response.index('```', start)
        response = response[start:end].strip()
    elif '```' in response:
        start = response.index('```') + 3
        end = response.index('```', start)
        response = response[start:end].strip()

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return None
