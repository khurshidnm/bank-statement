import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.target_schema import StandardizedDataset, TargetRecord

client = TestClient(app)


@pytest.fixture
def mock_ai_mapper(monkeypatch):
    def _fake_mapper(rows, source_columns):
        return StandardizedDataset(
            records=[
                TargetRecord(
                    record_id="REC-001",
                    customer_name="Acme Corporation",
                    email="contact@acme.com",
                    transaction_amount=1450.75,
                    transaction_date="2026-08-10",
                    status="completed",
                )
                for _ in rows
            ]
        )

    monkeypatch.setattr("app.api.v1.transform.map_rows_to_target_schema", _fake_mapper)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_transform_csv_success(mock_ai_mapper):
    csv_content = b"Cust_Name,Txn_Val,Email\nAcme Corp,1450.75,contact@acme.com\n"
    response = client.post(
        "/api/v1/transform",
        files={"file": ("sample.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["total_records_processed"] == 1
    assert body["data"][0]["customer_name"] == "Acme Corporation"


def test_transform_unsupported_file_type(mock_ai_mapper):
    response = client.post(
        "/api/v1/transform",
        files={"file": ("sample.txt", b"not a spreadsheet", "text/plain")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "UNSUPPORTED_FILE_TYPE"


def test_transform_empty_file(mock_ai_mapper):
    response = client.post(
        "/api/v1/transform",
        files={"file": ("empty.csv", b"Name,Email\n", "text/csv")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"]["error_code"] == "EMPTY_FILE"
