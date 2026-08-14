import datetime

import pytest

from app.services.bank_statement.parsing_utils import (
    find_account_number,
    find_currency,
    is_time_only,
    merge_date_and_time,
    parse_amount,
    parse_datetime_cell,
    split_combined_counterparty,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, 0.0),
        ("", 0.0),
        (1735000, 1735000.0),
        (1735000.5, 1735000.5),
        ("1,735,000.00", 1735000.0),  # comma=thousands, dot=decimal
        ("5 950 635,65", 5950635.65),  # space=thousands, comma=decimal
        ("6 048 000,00", 6048000.0),
        ("0,77", 0.77),
        ("300", 300.0),
        (".00", 0.0),
        ("-", 0.0),
    ],
)
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


def test_parse_datetime_cell_from_native_timestamp():
    assert parse_datetime_cell(datetime.datetime(2025, 8, 1, 16, 7, 0)) == "01.08.2025 16:07:00"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("01.08.2025 16:07:00", "01.08.2025 16:07:00"),
        ("28.02.2025", "28.02.2025 00:00:00"),
        ("05.01.26", "05.01.2026 00:00:00"),
        ("2019-01-11 00:00:00", "11.01.2019 00:00:00"),
        ("not a date", None),
        (None, None),
    ],
)
def test_parse_datetime_cell_from_strings(raw, expected):
    assert parse_datetime_cell(raw) == expected


def test_is_time_only():
    assert is_time_only("08:54:22")
    assert is_time_only("8:54")
    assert not is_time_only("06.01.2025")
    assert not is_time_only(None)


def test_merge_date_and_time():
    assert merge_date_and_time("06.01.2025 00:00:00", "08:54:22") == "06.01.2025 08:54:22"
    assert merge_date_and_time("06.01.2025 00:00:00", "not a time") == "06.01.2025 00:00:00"


def test_split_combined_counterparty_slash_form():
    raw = '16401000505674759001/310644704/TOShKENT Sh. AT "ALOQABANK" BOSh OFISI'
    bank_code, account, name = split_combined_counterparty(raw)
    assert bank_code == ""
    assert account == "16401000505674759001"
    assert name == raw  # full raw string retained per the target contract


def test_split_combined_counterparty_labeled_form():
    raw = "МФО:00401 Счет:20208000000966048001 ИНН:305975326 Some Company LLC"
    bank_code, account, name = split_combined_counterparty(raw)
    assert bank_code == "00401"
    assert account == "20208000000966048001"
    assert name == "Some Company LLC"


def test_find_account_number():
    assert find_account_number("Лицевой счет: 20208000105674759001") == "20208000105674759001"
    assert find_account_number("no account here") is None


def test_find_currency_defaults_to_uzs():
    assert find_currency("no currency mentioned") == "UZS"
    assert find_currency("Валюта счета: USD") == "USD"
