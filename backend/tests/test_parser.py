import io
import json

import pandas as pd
import pytest

from app.services.file_parser import (
    EmptyFileError,
    UnsupportedFileTypeError,
    parse_file,
    sample_rows,
)


def test_parse_csv():
    csv_bytes = b"Name,Email,Amount\nAcme Corp,contact@acme.com,1250.00\n"
    parsed = parse_file("sample.csv", csv_bytes)

    assert parsed.row_count == 1
    assert parsed.source_columns == ["Name", "Email", "Amount"]


def test_parse_json_list_of_records():
    payload = json.dumps([
        {"customer": "Acme", "amount": 100},
        {"customer": "Globex", "amount": 200},
    ]).encode("utf-8")
    parsed = parse_file("sample.json", payload)

    assert parsed.row_count == 2


def test_parse_json_wrapped_in_data_key():
    payload = json.dumps({"data": [{"customer": "Acme", "amount": 100}]}).encode("utf-8")
    parsed = parse_file("sample.json", payload)

    assert parsed.row_count == 1


def test_parse_excel():
    df = pd.DataFrame({"Cust_Name": ["Acme"], "Txn_Val": [1450.75]})
    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    parsed = parse_file("sample.xlsx", buffer.read())

    assert parsed.row_count == 1
    assert "Cust_Name" in parsed.source_columns


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        parse_file("sample.txt", b"irrelevant")


def test_empty_csv_raises():
    with pytest.raises(EmptyFileError):
        parse_file("empty.csv", b"Name,Email,Amount\n")


def test_sample_rows_respects_max_rows():
    csv_bytes = ("Name,Amount\n" + "\n".join(f"Row{i},{i}" for i in range(20))).encode("utf-8")
    parsed = parse_file("sample.csv", csv_bytes)

    rows = sample_rows(parsed, max_rows=15)

    assert len(rows) == 15
