import datetime
import io

import openpyxl
import pytest

from app.services.bank_statement.engine import BankStatementParseError
from app.services.bank_statement.transform import parse_bank_statement
from app.services.file_parser import UnsupportedFileTypeError


def _build_xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_flat_layout_with_separate_counterparty_columns():
    rows = [
        ["История по счету 20208000100191503001"],
        ["Счет клиента", "Наименование клиента", "Счет кореспондента", "Наименование кореспондента",
         "Транзакционный номер", "МФО", "Сумма дебита", "Сумма кредита", "Дата", "Назначение платежа"],
        ["20208000100191503001", "ООО RAXIMBOY OTA", "20208000600800034001", "OOO TERASSO CHICKEN",
         "2418659625", "1069", 0, 201600000, datetime.datetime(2025, 1, 6, 15, 50, 6), "Оплата за товар"],
        ["20208000100191503001", "ООО RAXIMBOY OTA", "16309000800191503003", "MCHJ RAXIMBOY OTA",
         "2421372741", "1095", 1451704.11, 0, datetime.datetime(2025, 1, 8, 15, 49, 58), "Погашение процента"],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    assert stmt.account_number == "20208000100191503001"
    assert stmt.currency == "UZS"
    assert stmt.transaction_count == 2
    assert stmt.total_credit == pytest.approx(201600000.0)
    assert stmt.total_debit == pytest.approx(1451704.11)

    first = stmt.transactions[0]
    assert first.transaction_date == "06.01.2025 15:50:06"
    assert first.document_number == "2418659625"
    assert first.counterparty_account == "20208000600800034001"
    assert first.counterparty_name == "OOO TERASSO CHICKEN"
    assert first.bank_code == "1069"
    assert first.credit_amount == pytest.approx(201600000.0)


def test_combined_slash_form_counterparty_column():
    rows = [
        ["Счет: 20208000105674759001 SOME COMPANY LLC"],
        ["Дата", "Счет/ИНН", "№ док-та", "Оп", "МФО", "Оборот Дебет", "Оборот Кредит", "Назначение платежа"],
        ["03.10.2025 16:39:42", '20214000205122905002/306712636/АО "HAYOT BIRJA"', "1000544217", "21",
         "00974", 0, 16000000, "Вывод средств от торгов"],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    assert stmt.account_number == "20208000105674759001"
    txn = stmt.transactions[0]
    assert txn.counterparty_account == "20214000205122905002"
    assert txn.counterparty_name == '20214000205122905002/306712636/АО "HAYOT BIRJA"'
    assert txn.bank_code == "00974"


def test_own_vs_counterparty_account_disambiguation():
    # Bare "Счет" header is ambiguous: here it holds the OWN account on every row,
    # so it must be ignored rather than mistaken for the counterparty's account.
    rows = [
        ["История по счету: 20208000205032606001"],
        ["Регион", "Филиал", "Счет", "Дата", "Счет корреспондента", "Наименование корреспондента",
         "МФО", "Наименование банка корреспондента", "№ документа", "Сумма дебет", "Сумма кредит"],
        ["03-АНДИЖОН", "00079", "20208000205032606001", "04.01.2021", "23510000905032606001",
         "MOYGIR SAVDO", "00079", "Bank Name", "948902250", 0, 83532.6],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    txn = stmt.transactions[0]
    assert txn.counterparty_account == "23510000905032606001"
    assert txn.counterparty_name == "MOYGIR SAVDO"


def test_metadata_rows_sandwiched_after_header():
    # agrobank/davrbank quirk: the account-number line appears *after* the header
    # row, before the real transaction rows begin.
    rows = [
        ["ДАТА", "СЧЕТ", "Наименование счета", "N док-та", "ВО", "МФО", "Оборот Дебет", "Оборот Кредит",
         "Назначение платежа", "Кас.смв"],
        ["00045-BANK NAME"],
        ["Счет: 20208000905190167001 SOME FARM LLC"],
        ["Остаток на начало периода"],
        ["31.03.20", "23510000905190167200", "Counterparty Name", "015", "06", "00045", 0, 7001,
         "Payment purpose text", None],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    assert stmt.account_number == "20208000905190167001"
    assert stmt.transaction_count == 1
    assert stmt.transactions[0].counterparty_account == "23510000905190167200"


def test_multirow_layout_merges_continuation_rows():
    rows = [
        ["Лицевой счет No 20208000505703819001"],
        ["Дата проводки", "N документа", "Оп", "Корреспондент: Банк/Счет/ИНН Наименование", "Дебет", "Кредит"],
        ["06.01.2025", "79", "21", "МФО:00401 Счет:20208000000966048001 ИНН:305975326", 1735000, 0],
        ["08:54:22", None, None, "ООО Дирекция Технологического парка", None, None],
        [None, None, None, "00668~Офертага асосан платеж", None, None],
        ["06.01.2025", "80", "21", "МФО:00997 Счет:23120000800000997001 ИНН:123456789", 3520000, 0],
        ["15:45:16", None, None, "Some Other Company", None, None],
        [None, None, None, "00634~Another purpose", None, None],
        # a third transaction with only one continuation row (no separate purpose line)
        ["07.01.2025", "81", "21", "МФО:00401 Счет:20208000000966048002 ИНН:305975327", 0, 500000],
        ["09:00:00", None, None, "Third Company Name", None, None],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    assert stmt.transaction_count == 3
    first = stmt.transactions[0]
    assert first.transaction_date == "06.01.2025 08:54:22"
    assert first.bank_code == "00401"
    assert first.counterparty_account == "20208000000966048001"
    assert first.counterparty_name == "ООО Дирекция Технологического парка"
    assert first.payment_purpose == "00668~Офертага асосан платеж"

    third = stmt.transactions[2]
    assert third.transaction_date == "07.01.2025 09:00:00"
    assert third.counterparty_name == "Third Company Name"
    assert third.payment_purpose == ""


def test_subtotal_and_blank_filler_rows_are_skipped():
    rows = [
        ["№ счёта: 20208000305239709001"],
        ["№ пп", "Дата документа", "№ док.", "Наименование счёта", "МФО", "Обороты по дебету",
         "Обороты по кредиту", "Назначение платежа"],
        ["216", "20.02.2023", "2748521854", "Some Payer", "00014", 0, 6048000, "Payment 1"],
        [None, None, None, None, None, None, None, None],  # merged-cell filler row
        ["217", "20.02.2023", None, "Итого за 20.02.2023", None, 0, 6048000, "Daily subtotal"],
        ["218", "21.02.2023", "2748521856", "Some Payer 2", "00014", 0, 14112000, "Payment 2"],
    ]
    stmt = parse_bank_statement("statement.xlsx", _build_xlsx(rows))

    assert stmt.transaction_count == 2
    assert {t.document_number for t in stmt.transactions} == {"2748521854", "2748521856"}


def test_unrecognized_layout_raises():
    rows = [["just", "some", "random", "spreadsheet", "data"], [1, 2, 3, 4, 5]]
    with pytest.raises(BankStatementParseError):
        parse_bank_statement("statement.xlsx", _build_xlsx(rows))


def test_unsupported_extension_raises():
    with pytest.raises(UnsupportedFileTypeError):
        parse_bank_statement("statement.pdf", b"irrelevant")


def test_html_disguised_as_xls():
    html = """
    <html><head><meta http-equiv="Content-Type" content="text/html; charset=windows-1251"/></head>
    <body>
    <table><tr><td>Лицевой счет No 20208000600754215001</td></tr></table>
    <table>
      <tr><td>Дата/время проводки</td><td>Номер документа</td><td>Оп</td>
          <td>Корреспондент: Банк / Счет / ИНН  Наименование</td><td>Дебет</td><td>Кредит</td></tr>
      <tr><td>12.01.2026 08:52:51</td><td>36</td><td>21</td>
          <td>МФО:00014 Счет:23402000300100001010 ИНН:201122919 Ministry Of Finance</td>
          <td>1,071,000.00</td><td>.00</td></tr>
    </table>
    </body></html>
    """.encode("cp1251")
    stmt = parse_bank_statement("statement.xls", html)

    assert stmt.account_number == "20208000600754215001"
    txn = stmt.transactions[0]
    assert txn.bank_code == "00014"
    assert txn.counterparty_account == "23402000300100001010"
    assert txn.counterparty_name == "Ministry Of Finance"
    assert txn.debit_amount == pytest.approx(1071000.0)
    assert txn.credit_amount == pytest.approx(0.0)
