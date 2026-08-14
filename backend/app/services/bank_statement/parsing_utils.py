import datetime
import re
from typing import Optional

import pandas as pd

ACCOUNT_NUMBER_RE = re.compile(r"\b\d{20}\b")
CURRENCY_RE = re.compile(r"валют[а-яё]*\s*(?:счета)?\s*[:\-]?\s*([A-Za-zА-Яа-яЁё]{3})", re.IGNORECASE)
TIME_ONLY_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

_DATE_FORMATS = (
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%d.%m.%y %H:%M:%S",
    "%d.%m.%y %H:%M",
    "%d.%m.%y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def cell_text(value) -> str:
    if is_blank(value):
        return ""
    if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
        return str(value)
    return str(value).strip()


def parse_amount(value) -> float:
    """Parse a numeric cell that may be a native number or a locale-formatted string
    using either ',' or '.' (or both, in either order) as the thousands/decimal separator."""
    if is_blank(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace("\xa0", " ").replace(" ", "")
    if not s or s.lower() in ("nan", "none", "-"):
        return 0.0

    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        parts = s.split(",")
        s = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) == 2 else "".join(parts)

    try:
        return float(s)
    except ValueError:
        return 0.0


def is_time_only(value) -> bool:
    text = cell_text(value)
    return bool(TIME_ONLY_RE.match(text))


def parse_datetime_cell(value) -> Optional[str]:
    """Return a value formatted as 'DD.MM.YYYY HH:MM:SS', or None if unparseable.
    Rows lacking a time component are padded with 00:00:00."""
    if is_blank(value):
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    if isinstance(value, datetime.datetime):
        return value.strftime("%d.%m.%Y %H:%M:%S")
    if isinstance(value, datetime.date):
        return value.strftime("%d.%m.%Y 00:00:00")

    text = cell_text(value)
    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
        return parsed.strftime("%d.%m.%Y %H:%M:%S")
    return None


def merge_date_and_time(date_str: str, time_value) -> str:
    """Combine a 'DD.MM.YYYY 00:00:00' date with a separately-provided 'HH:MM:SS' cell."""
    time_text = cell_text(time_value)
    if not TIME_ONLY_RE.match(time_text):
        return date_str
    if len(time_text.split(":")) == 2:
        time_text += ":00"
    return f"{date_str[:10]} {time_text}"


_LABELED_CORRESPONDENT_RE = re.compile(
    r"МФО\s*:?\s*(\d+)[^\d]*Счет\s*:?\s*(\d+)[^\d]*ИНН\s*:?\s*(\d+)\s*(.*)",
    re.IGNORECASE | re.DOTALL,
)


def split_combined_counterparty(raw: str) -> tuple[str, str, str]:
    """Splits a combined correspondent cell into (bank_code, account, name).
    Handles two formats seen in the wild: the compact 'account/inn/name' form (per
    the target contract, name keeps the full raw string in this case), and the
    labeled 'МФО:x Счет:y ИНН:z <name>' prose form used by some export templates,
    which also doubles as a bank_code source when no dedicated MFO column exists."""
    raw = (raw or "").strip()
    labeled = _LABELED_CORRESPONDENT_RE.match(raw)
    if labeled:
        bank_code, account, _inn, name = labeled.groups()
        return bank_code, account, (name.strip() or raw)

    first_segment = raw.split("/", 1)[0].strip()
    account = first_segment if first_segment.isdigit() else ""
    return "", account, raw


def find_account_number(text_blob: str) -> Optional[str]:
    match = ACCOUNT_NUMBER_RE.search(text_blob)
    return match.group(0) if match else None


def find_currency(text_blob: str) -> str:
    match = CURRENCY_RE.search(text_blob)
    return match.group(1).upper() if match else "UZS"
