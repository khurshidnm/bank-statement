import json
import logging
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services.bank_statement.layout import LayoutSpec
from app.services.bank_statement.parsing_utils import cell_text, find_account_number, find_currency

logger = logging.getLogger(__name__)

ColumnRoleName = Literal[
    "date",
    "document_number",
    "debit",
    "credit",
    "bank_code",
    "payment_purpose",
    "counterparty_account",
    "counterparty_name",
    "combined_counterparty",
]

SYSTEM_PROMPT = """You are a structural analyzer for bank account statement exports. You receive a raw \
grid dump (row index: cell values) of a spreadsheet or HTML table exported from a bank's client cabinet. \
These exports are inconsistent across banks: header row position varies, column order varies, some banks \
combine a correspondent's account/INN/name into a single cell (formats like "account/inn/name" or \
"МФО:x Счет:y ИНН:z name"), and a few spread one transaction across multiple physical rows (e.g. date and \
amount on one row, the counterparty name on the next, the payment purpose on the row after that — \
recognizable by continuation rows containing only a bare time value like '08:54:22' with no document number).

Your job is NOT to transcribe any transaction data. You only describe the STRUCTURE: which row is the \
header, which row real transaction data starts on, where the account number appears, and which column \
index maps to which semantic role. A downstream program uses your structural description to extract the \
actual figures programmatically — so precision about row/column INDICES matters far more than anything else.

Roles you may assign to columns:
- date: the transaction date (and possibly time)
- document_number: the transaction/document reference number (not a mere row-sequence counter like "No"/"№ пп")
- debit: debit/outgoing amount column
- credit: credit/incoming amount column
- bank_code: the correspondent bank's MFO/BIC/SWIFT code (only if it has its own column)
- payment_purpose: the payment purpose/description text
- counterparty_account: the correspondent's account number (only when it has its own separate column)
- counterparty_name: the correspondent's name (only when it has its own separate column)
- combined_counterparty: a single column that packs the correspondent's account, INN, and name together

Do not assign a role to columns describing the statement OWNER's own account/name/branch — only the \
transaction counterparty and the transaction fields themselves. Leave ambiguous or irrelevant columns \
unassigned."""


class ColumnRole(BaseModel):
    column_index: int
    role: ColumnRoleName


class InferredLayout(BaseModel):
    header_row_index: int
    data_start_row_index: int
    account_number: Optional[str] = Field(None, description="20-digit account number if visible in the sample")
    currency: str = "UZS"
    is_multirow: bool = Field(
        False, description="True if one transaction's fields spill across multiple physical rows"
    )
    columns: list[ColumnRole]


def _grid_to_text(grid: pd.DataFrame, max_rows: int = 40, max_cols: int = 30) -> str:
    lines = []
    n_rows = min(max_rows, len(grid))
    n_cols = min(max_cols, grid.shape[1])
    for r in range(n_rows):
        cells = [cell_text(grid.iat[r, c])[:60] for c in range(n_cols)]
        lines.append(f"{r}: {cells}")
    return "\n".join(lines)


def _call_openai(sample_text: str, api_key: str) -> Optional[InferredLayout]:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Raw grid sample (row_index: [cell0, cell1, ...]):\n{sample_text}"},
        ],
        response_format=InferredLayout,
    )
    message = completion.choices[0].message
    if message.refusal or message.parsed is None:
        return None
    return message.parsed


def _call_anthropic(sample_text: str, api_key: str) -> Optional[InferredLayout]:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    tool_schema = InferredLayout.model_json_schema()
    response = client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[{"name": "emit_layout", "description": "Return the inferred layout.", "input_schema": tool_schema}],
        tool_choice={"type": "tool", "name": "emit_layout"},
        messages=[
            {"role": "user", "content": f"Raw grid sample (row_index: [cell0, cell1, ...]):\n{sample_text}"}
        ],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "emit_layout":
            return InferredLayout.model_validate(block.input)
    return None


def infer_layout_with_ai(grid: pd.DataFrame) -> Optional[LayoutSpec]:
    """Fallback for files the deterministic header/column detector couldn't recognize.
    Asks an LLM to describe the structure only (header row, column roles) — never to
    transcribe transaction data itself — then hands that spec back to the same
    deterministic extraction code the rest of the pipeline uses."""
    settings = get_settings()
    sample_text = _grid_to_text(grid)

    try:
        if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
            inferred = _call_anthropic(sample_text, settings.anthropic_api_key)
        elif settings.openai_api_key:
            inferred = _call_openai(sample_text, settings.openai_api_key)
        else:
            return None
    except Exception:
        logger.exception("AI layout inference failed")
        return None

    if inferred is None:
        return None

    columns: dict[str, int] = {}
    combined = False
    for col_role in inferred.columns:
        if col_role.role == "combined_counterparty":
            combined = True
            columns["combined_counterparty"] = col_role.column_index
        elif col_role.role not in columns:
            columns[col_role.role] = col_role.column_index

    if "date" not in columns or ("debit" not in columns and "credit" not in columns):
        return None

    account_number = inferred.account_number
    currency = inferred.currency or "UZS"
    if not account_number:
        preamble_rows = list(range(inferred.header_row_index)) + list(
            range(inferred.header_row_index + 1, inferred.data_start_row_index)
        )
        preamble_text = "\n".join(
            cell_text(grid.iat[r, c]) for r in preamble_rows for c in range(grid.shape[1]) if r < len(grid)
        )
        account_number = find_account_number(preamble_text)
        if currency == "UZS":
            currency = find_currency(preamble_text)

    return LayoutSpec(
        header_row=inferred.header_row_index,
        data_start_row=inferred.data_start_row_index,
        columns=columns,
        combined_counterparty=combined,
        account_number=account_number,
        currency=currency,
        score=0.0,
        ai_multirow=inferred.is_multirow,
    )
