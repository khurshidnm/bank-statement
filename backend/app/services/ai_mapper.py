import json

from app.config import get_settings
from app.models.target_schema import StandardizedDataset

SYSTEM_PROMPT = """You are a strict data-normalization engine. You receive a sample of rows from an \
arbitrary spreadsheet, CSV, or JSON export with unpredictable column names, layouts, and formats. \
Your job is to semantically map each row's fields onto the target schema, cleaning and \
type-casting values as you go:
- Standardize all dates to ISO 8601 (YYYY-MM-DD).
- Strip currency symbols and thousands separators from numeric amounts (e.g. "$1,250.00" -> 1250.00).
- Trim whitespace and normalize email addresses to lowercase.
- Infer a stable record_id when the source has no obvious unique identifier.
- Never invent customer data that is not implied by the source row.
Return every input row as exactly one output record, in the same order."""


class AIMappingError(Exception):
    pass


def _build_user_prompt(rows: list[dict], source_columns: list[str]) -> str:
    return (
        f"Source columns detected: {source_columns}\n\n"
        f"Rows to map ({len(rows)} total):\n"
        f"{json.dumps(rows, default=str, indent=2)}"
    )


def map_rows_to_target_schema(rows: list[dict], source_columns: list[str]) -> StandardizedDataset:
    """Send sampled/full rows to the configured LLM and parse the result into StandardizedDataset."""
    settings = get_settings()
    user_prompt = _build_user_prompt(rows, source_columns)

    if settings.ai_provider == "anthropic":
        return _map_with_anthropic(user_prompt, settings.anthropic_api_key)
    return _map_with_openai(user_prompt, settings.openai_api_key)


def _map_with_openai(user_prompt: str, api_key: str) -> StandardizedDataset:
    if not api_key:
        raise AIMappingError("OPENAI_API_KEY is not configured.")

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format=StandardizedDataset,
    )
    message = completion.choices[0].message
    if message.refusal:
        raise AIMappingError(f"Model refused to map data: {message.refusal}")
    if message.parsed is None:
        raise AIMappingError("Model returned no parsed structured output.")
    return message.parsed


def _map_with_anthropic(user_prompt: str, api_key: str) -> StandardizedDataset:
    if not api_key:
        raise AIMappingError("ANTHROPIC_API_KEY is not configured.")

    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    tool_schema = StandardizedDataset.model_json_schema()
    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[{"name": "emit_standardized_dataset", "description": "Return the mapped dataset.", "input_schema": tool_schema}],
        tool_choice={"type": "tool", "name": "emit_standardized_dataset"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "emit_standardized_dataset":
            return StandardizedDataset.model_validate(block.input)
    raise AIMappingError("Model response did not include the expected tool call.")
