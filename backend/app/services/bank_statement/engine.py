import pandas as pd

from app.models.bank_statement_schema import BankStatement, BankTransaction
from app.services.bank_statement.layout import LayoutSpec, normalize
from app.services.bank_statement.parsing_utils import (
    cell_text,
    parse_amount,
    parse_datetime_cell,
    split_combined_counterparty,
)


class BankStatementParseError(Exception):
    pass


def _row_text(grid: pd.DataFrame, row_idx: int, col: int | None) -> str:
    if col is None or col >= grid.shape[1]:
        return ""
    return cell_text(grid.iat[row_idx, col])


def extract_transactions(grid: pd.DataFrame, layout: LayoutSpec) -> list[BankTransaction]:
    columns = layout.columns
    has_doc_col = "document_number" in columns
    transactions: list[BankTransaction] = []

    for row_idx in range(layout.data_start_row, len(grid)):
        date_col = columns.get("date")
        transaction_date = parse_datetime_cell(grid.iat[row_idx, date_col]) if date_col is not None else None
        if not transaction_date:
            continue

        document_number = _row_text(grid, row_idx, columns.get("document_number"))
        if has_doc_col and not document_number:
            continue

        purpose = _row_text(grid, row_idx, columns.get("payment_purpose"))
        raw_name_for_skip_check = _row_text(grid, row_idx, columns.get("counterparty_name"))
        if normalize(purpose).startswith("итого") or normalize(raw_name_for_skip_check).startswith("итого"):
            continue

        debit_amount = parse_amount(grid.iat[row_idx, columns["debit"]]) if "debit" in columns else 0.0
        credit_amount = parse_amount(grid.iat[row_idx, columns["credit"]]) if "credit" in columns else 0.0

        combined_bank_code = ""
        if layout.combined_counterparty and "combined_counterparty" in columns:
            raw_combined = _row_text(grid, row_idx, columns["combined_counterparty"])
            combined_bank_code, counterparty_account, counterparty_name = split_combined_counterparty(
                raw_combined
            )
        else:
            counterparty_account = _row_text(grid, row_idx, columns.get("counterparty_account"))
            counterparty_name = _row_text(grid, row_idx, columns.get("counterparty_name"))

        bank_code = _row_text(grid, row_idx, columns.get("bank_code")) or combined_bank_code

        transactions.append(
            BankTransaction(
                transaction_date=transaction_date,
                document_number=document_number,
                credit_amount=credit_amount,
                debit_amount=debit_amount,
                counterparty_name=counterparty_name,
                counterparty_account=counterparty_account,
                bank_code=bank_code,
                payment_purpose=purpose,
            )
        )

    return transactions


def build_statement(layout: LayoutSpec, transactions: list[BankTransaction]) -> BankStatement:
    if not layout.account_number:
        raise BankStatementParseError("Could not determine the account number for this statement.")
    if not transactions:
        raise BankStatementParseError("No transactions could be extracted from this file.")

    return BankStatement(
        account_number=layout.account_number,
        currency=layout.currency,
        transaction_count=len(transactions),
        total_credit=sum(t.credit_amount for t in transactions),
        total_debit=sum(t.debit_amount for t in transactions),
        transactions=transactions,
    )
