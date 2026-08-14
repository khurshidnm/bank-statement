from unittest.mock import MagicMock, patch

from app.services.ai_mapper import _coerce_stringified_records, _map_with_anthropic


def test_coerce_stringified_records_parses_bare_array_string():
    malformed = {"records": '[{"record_id": "REC-001", "customer_name": "Acme"}]'}
    coerced = _coerce_stringified_records(malformed)
    assert coerced["records"] == [{"record_id": "REC-001", "customer_name": "Acme"}]


def test_coerce_stringified_records_parses_double_wrapped_object_string():
    # The shape actually observed in production: Claude stringifies the *entire*
    # outer object, with "records" nested inside the string again, rather than
    # just stringifying the bare array.
    malformed = {"records": '{"records": [{"record_id": "REC-001", "customer_name": "Acme"}]}'}
    coerced = _coerce_stringified_records(malformed)
    assert coerced["records"] == [{"record_id": "REC-001", "customer_name": "Acme"}]


def test_coerce_stringified_records_unwraps_multiple_nesting_levels():
    malformed = {"records": '{"records": "{\\"records\\": [{\\"record_id\\": \\"REC-001\\"}]}"}'}
    coerced = _coerce_stringified_records(malformed)
    assert coerced["records"] == [{"record_id": "REC-001"}]


def test_coerce_stringified_records_leaves_native_list_untouched():
    already_correct = {"records": [{"record_id": "REC-001"}]}
    assert _coerce_stringified_records(already_correct) is already_correct


def test_coerce_stringified_records_leaves_unparseable_string_untouched():
    broken = {"records": "not valid json"}
    assert _coerce_stringified_records(broken) == broken


def _fake_tool_use_block(input_dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = "emit_standardized_dataset"
    block.input = input_dict
    return block


def test_map_with_anthropic_recovers_from_stringified_records_field():
    # Reproduces the real failure observed in production: Claude returned the
    # "records" array JSON-encoded as a string instead of natively, which used
    # to raise "Input should be a valid list [type=list_type]" from Pydantic.
    stringified_records = (
        '[{"record_id": "REC-001", "customer_name": "Acme Corporation", '
        '"email": "contact@acme.com", "transaction_amount": 1450.75, '
        '"transaction_date": "2026-08-10", "status": "completed"}]'
    )
    fake_response = MagicMock()
    fake_response.content = [_fake_tool_use_block({"records": stringified_records})]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("anthropic.Anthropic", return_value=fake_client):
        result = _map_with_anthropic("irrelevant prompt", "fake-api-key")

    assert len(result.records) == 1
    assert result.records[0].record_id == "REC-001"
    assert result.records[0].customer_name == "Acme Corporation"


def test_map_with_anthropic_recovers_from_double_wrapped_records_field():
    double_wrapped = (
        '{"records": [{"record_id": "REC-001", "customer_name": "Acme Corporation", '
        '"email": "contact@acme.com", "transaction_amount": 1450.75, '
        '"transaction_date": "2026-08-10", "status": "completed"}]}'
    )
    fake_response = MagicMock()
    fake_response.content = [_fake_tool_use_block({"records": double_wrapped})]

    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_response

    with patch("anthropic.Anthropic", return_value=fake_client):
        result = _map_with_anthropic("irrelevant prompt", "fake-api-key")

    assert len(result.records) == 1
    assert result.records[0].record_id == "REC-001"
