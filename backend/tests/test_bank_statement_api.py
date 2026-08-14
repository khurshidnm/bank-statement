import datetime
import io

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.api.v1.bank_statement import TEMPLATE_REQUIRED_MESSAGE
from app.main import app

client = TestClient(app)


def _build_xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_transform_success():
    rows = [
        ["Счет: 20208000105674759001 SOME COMPANY LLC"],
        ["Дата", "Счет/ИНН", "№ док-та", "Оп", "МФО", "Оборот Дебет", "Оборот Кредит", "Назначение платежа"],
        [datetime.datetime(2025, 10, 3, 16, 39, 42), '20214000205122905002/306712636/АО "HAYOT BIRJA"',
         "1000544217", "21", "00974", 0, 16000000, "Вывод средств от торгов"],
    ]
    response = client.post(
        "/api/v1/bank-statement/transform",
        files={"file": ("statement.xlsx", _build_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_number"] == "20208000105674759001"
    assert body["transaction_count"] == 1


def test_unrecognized_layout_returns_template_message():
    rows = [["just", "some", "random", "spreadsheet", "data"], [1, 2, 3, 4, 5]]
    response = client.post(
        "/api/v1/bank-statement/transform",
        files={"file": ("statement.xlsx", _build_xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "BANK_STATEMENT_PARSE_FAILED"
    assert detail["message"] == TEMPLATE_REQUIRED_MESSAGE


def test_unsupported_file_type_returns_template_message():
    response = client.post(
        "/api/v1/bank-statement/transform",
        files={"file": ("statement.pdf", b"not a spreadsheet", "application/pdf")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "UNSUPPORTED_FILE_TYPE"
    assert detail["message"] == TEMPLATE_REQUIRED_MESSAGE


def test_file_too_large_keeps_its_own_message():
    from app.config import get_settings

    settings = get_settings()
    oversized = b"0" * (settings.max_upload_bytes + 1)
    response = client.post(
        "/api/v1/bank-statement/transform",
        files={"file": ("statement.xlsx", oversized, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_code"] == "FILE_TOO_LARGE"
    assert detail["message"] != TEMPLATE_REQUIRED_MESSAGE
