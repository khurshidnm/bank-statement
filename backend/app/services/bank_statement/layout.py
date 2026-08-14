import re
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from app.services.bank_statement.parsing_utils import (
    cell_text,
    find_account_number,
    find_currency,
    parse_datetime_cell,
)

_DUP_LETTER_RE = re.compile(r"(.)\1+")
_APOSTROPHE_RE = re.compile(r"[\'‘’ʻʼ`]")


def normalize(text: str) -> str:
    """Lowercases, strips apostrophe variants and whitespace, folds ё->е, and collapses
    doubled letters so that spelling/spacing drift between bank export templates (e.g.
    'корреспондента' vs the common typo 'кореспондента', 'счёт' vs 'счет', or
    'Счет/ИНН' vs 'Счет / ИНН') doesn't break header matching. Applied identically to
    both header cell text and the phrase constants below, so this only ever makes
    matching more forgiving, never introduces asymmetric false positives."""
    text = _APOSTROPHE_RE.sub("", text.lower()).replace("ё", "е")
    text = re.sub(r"\s+", "", text)
    return _DUP_LETTER_RE.sub(r"\1", text)


# Ordered (role, phrase) pairs, written with natural/correct spelling — both sides of
# the comparison are run through normalize() at match time, so minor spelling drift
# between bank templates (missing double letters, stray apostrophes) doesn't matter.
# More specific / longer phrases are placed before shorter ones they could collide with.
_ROLE_PHRASES_RAW: list[tuple[str, str]] = [
    ("combined_counterparty", "счет/инн"),
    ("combined_counterparty", "cчет/инн"),  # note: Latin "C" — a real homoglyph typo seen in mkb.xls

    ("ignore", "счет клиента"),
    ("ignore", "наименование клиента"),
    ("ignore", "наименование банка"),
    ("ignore", "регион"),
    ("ignore", "кас.смв"),
    ("ignore", "кассовый символ"),
    ("ignore", "вид операции"),
    ("ignore", "вид док"),
    ("ignore", "тип документа"),

    ("date", "дата/время проводки"),
    ("date", "дата документа"),
    ("date", "дата проводки"),
    ("date", "sana"),
    ("date", "дата"),
    ("date", "date"),

    ("ignore", "№ пп"),

    ("document_number", "транзакционный номер"),
    ("document_number", "документ"),
    ("document_number", "док"),
    ("document_number", "dok"),

    ("debit", "сумма дебита"),
    ("debit", "сумма дебет"),
    ("debit", "оборот дебет"),
    ("debit", "обороты по дебету"),
    ("debit", "дебетовый оборот"),
    ("debit", "дебет"),
    ("debit", "debet"),

    ("credit", "сумма кредита"),
    ("credit", "сумма кредит"),
    ("credit", "оборот кредит"),
    ("credit", "обороты по кредиту"),
    ("credit", "кредитовый оборот"),
    ("credit", "кредит"),
    ("credit", "kredit"),

    ("bank_code", "бик/swift"),
    ("bank_code", "бик"),
    ("bank_code", "swift"),
    ("bank_code", "мфо"),
    ("bank_code", "mfo"),

    # Name-phrases before account-phrases: "vakil hisob raqam nomi" contains
    # "vakil hisob raqam" as a substring and would otherwise lose its role.
    ("counterparty_name", "наименование корреспондента"),
    ("counterparty_name", "наименование контрагента"),
    ("counterparty_name", "наименование банка корреспондента"),
    ("counterparty_name", "vakil hisob raqam nomi"),

    ("counterparty_account", "счет корреспондента"),
    ("counterparty_account", "счет-корреспондент"),
    ("counterparty_account", "счет контрагента"),
    ("counterparty_account", "vakil hisob raqam"),

    ("payment_purpose", "назначение платежа"),
    ("payment_purpose", "назначение"),
    ("payment_purpose", "to'lov tafsilotlari"),
    ("payment_purpose", "tafsilot"),

    ("ignore", "инн"),
    ("ignore", "stir"),
]

_ROLE_PHRASES: list[tuple[str, str]] = [(role, normalize(phrase)) for role, phrase in _ROLE_PHRASES_RAW]
_AMBIGUOUS_ACCOUNT_PHRASES = [normalize(p) for p in ["счет", "cчет"]]
_AMBIGUOUS_NAME_PHRASES = [normalize(p) for p in ["наименование счета", "наименование"]]
_BANK_CODE_FALLBACK_PHRASES = [normalize(p) for p in ["филиал"]]
_EXACT_IGNORE = {normalize(p) for p in ["оп", "во", "код", "no", "n", "№"]}

REQUIRED_ROLES = {"date", "debit", "credit"}


@dataclass
class LayoutSpec:
    header_row: int
    data_start_row: int
    columns: dict = field(default_factory=dict)  # role -> column index
    combined_counterparty: bool = False
    account_number: Optional[str] = None
    currency: str = "UZS"
    score: float = 0.0
    bank_code_fallback_col: Optional[int] = None
    ai_multirow: Optional[bool] = None  # set only when this LayoutSpec came from the AI fallback


def _classify_header_cell(text: str) -> Optional[str]:
    normalized = normalize(text)
    if not normalized:
        return None
    if normalized in _EXACT_IGNORE:
        return "ignore"
    for role, phrase in _ROLE_PHRASES:
        if phrase in normalized:
            return role
    # Name-phrases are checked before account-phrases: "наименование счета" contains
    # "счет" as a substring (счет-а) and would otherwise be misread as an account column.
    for phrase in _AMBIGUOUS_NAME_PHRASES:
        if phrase in normalized:
            return "ambiguous_name"
    for phrase in _AMBIGUOUS_ACCOUNT_PHRASES:
        if phrase in normalized:
            return "ambiguous_account"
    for phrase in _BANK_CODE_FALLBACK_PHRASES:
        if phrase in normalized:
            return "bank_code_fallback"
    return None


def _score_row_as_header(grid: pd.DataFrame, row_idx: int) -> tuple[float, dict]:
    roles: dict[int, str] = {}
    for col in range(grid.shape[1]):
        text = cell_text(grid.iat[row_idx, col])
        role = _classify_header_cell(text)
        if role:
            roles[col] = role

    role_set = set(roles.values())
    score = 0.0
    for required in REQUIRED_ROLES:
        if required in role_set:
            score += 2.0
    if "combined_counterparty" in role_set:
        score += 2.0
    elif "counterparty_account" in role_set or "ambiguous_account" in role_set:
        score += 1.0
    if "bank_code" in role_set or "bank_code_fallback" in role_set:
        score += 1.0
    if "payment_purpose" in role_set:
        score += 1.0
    if "document_number" in role_set:
        score += 1.0
    return score, roles


def _resolve_ambiguous_columns(
    grid: pd.DataFrame, data_start_row: int, roles: dict, account_number: Optional[str]
) -> dict:
    resolved = dict(roles)
    ambiguous_account_cols = [c for c, r in roles.items() if r == "ambiguous_account"]
    ambiguous_name_cols = [c for c, r in roles.items() if r == "ambiguous_name"]
    sample = grid.iloc[data_start_row : data_start_row + 40]

    account_resolution: dict[int, str] = {}
    for col in ambiguous_account_cols:
        if col >= grid.shape[1]:
            continue
        values = [cell_text(v) for v in sample.iloc[:, col] if not pd.isna(v)]
        values = [v for v in values if v]
        if not values:
            resolved[col] = "ignore"
            account_resolution[col] = "ignore"
            continue
        if account_number:
            match_ratio = sum(1 for v in values if v == account_number) / len(values)
        else:
            match_ratio = 0.0
        role = "ignore" if match_ratio > 0.6 else "counterparty_account"
        resolved[col] = role
        account_resolution[col] = role

    has_counterparty_name = "counterparty_name" in roles.values()
    for col in ambiguous_name_cols:
        paired_role = None
        preceding_accounts = [c for c in account_resolution if c < col]
        if preceding_accounts:
            paired_role = account_resolution[max(preceding_accounts)]
        elif account_resolution:
            paired_role = next(iter(account_resolution.values()))

        if paired_role == "ignore":
            resolved[col] = "ignore"
        elif not has_counterparty_name:
            resolved[col] = "counterparty_name"
            has_counterparty_name = True
        else:
            resolved[col] = "ignore"

    role_values = set(resolved.values())
    if "bank_code" not in role_values:
        fallback_cols = [c for c, r in roles.items() if r == "bank_code_fallback"]
        if fallback_cols:
            resolved[fallback_cols[0]] = "bank_code"
            for c in fallback_cols[1:]:
                resolved[c] = "ignore"
    else:
        for c, r in list(resolved.items()):
            if r == "bank_code_fallback":
                resolved[c] = "ignore"

    return resolved


def detect_layout(grid: pd.DataFrame, max_header_search_rows: int = 30) -> Optional[LayoutSpec]:
    best_score, best_row, best_roles = 0.0, None, None
    search_limit = min(max_header_search_rows, len(grid))
    for row_idx in range(search_limit):
        score, roles = _score_row_as_header(grid, row_idx)
        if score > best_score:
            best_score, best_row, best_roles = score, row_idx, roles

    if best_row is None or best_score < 6.0:
        return None

    # Some export templates place metadata (account number, opening balance) *after*
    # the header row rather than before it. Scan forward for the first row whose date
    # column actually parses — everything between the header and there is preamble.
    date_col = best_roles and next((c for c, r in best_roles.items() if r == "date"), None)
    data_start_row = best_row + 1
    if date_col is not None:
        search_limit = min(best_row + 20, len(grid))
        for row_idx in range(best_row + 1, search_limit):
            if parse_datetime_cell(grid.iat[row_idx, date_col]):
                data_start_row = row_idx
                break

    preamble_rows = list(range(best_row)) + list(range(best_row + 1, data_start_row))
    preamble_text = "\n".join(
        cell_text(grid.iat[r, c]) for r in preamble_rows for c in range(grid.shape[1])
    )
    account_number = find_account_number(preamble_text)
    currency = find_currency(preamble_text)

    resolved_roles = _resolve_ambiguous_columns(grid, data_start_row, best_roles, account_number)

    if not account_number:
        for col, role in resolved_roles.items():
            if role == "ignore" and col in best_roles and best_roles[col] == "ambiguous_account":
                sample = grid.iloc[data_start_row : data_start_row + 10, col]
                for value in sample:
                    text = cell_text(value)
                    found = find_account_number(text)
                    if found:
                        account_number = found
                        break
            if account_number:
                break

    columns: dict[str, int] = {}
    combined = False
    for col, role in resolved_roles.items():
        if role in ("ignore", "ambiguous_account", "ambiguous_name", "bank_code_fallback"):
            continue
        if role == "combined_counterparty":
            combined = True
            columns["combined_counterparty"] = col
        elif role not in columns:
            columns[role] = col

    return LayoutSpec(
        header_row=best_row,
        data_start_row=data_start_row,
        columns=columns,
        combined_counterparty=combined,
        account_number=account_number,
        currency=currency,
        score=best_score,
    )
