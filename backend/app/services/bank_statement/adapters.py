import pandas as pd

from app.models.bank_statement_schema import BankTransaction
from app.services.bank_statement.layout import LayoutSpec
from app.services.bank_statement.parsing_utils import (
    cell_text,
    is_time_only,
    merge_date_and_time,
    parse_amount,
    parse_datetime_cell,
    split_combined_counterparty,
)


def _row_text(grid: pd.DataFrame, row_idx: int, col) -> str:
    if col is None or col >= grid.shape[1]:
        return ""
    return cell_text(grid.iat[row_idx, col])


def is_multirow_layout(grid: pd.DataFrame, layout: LayoutSpec) -> bool:
    """Some export templates (seen in ipotekabank-v1.xlsx) spread one transaction
    across several physical rows: date/doc-number/amount on the first row, the
    correspondent name on the next, and the payment purpose on the one after that.
    Recognizable by rows whose date column holds a bare time value (e.g. '08:54:22')
    rather than a full date — those are continuation rows, not new transactions."""
    date_col = layout.columns.get("date")
    doc_col = layout.columns.get("document_number")
    if date_col is None or doc_col is None:
        return False
    sample = grid.iloc[layout.data_start_row : layout.data_start_row + 60, date_col]
    time_only_hits = sum(1 for v in sample if is_time_only(v))
    return time_only_hits >= 3


def extract_multirow_transactions(grid: pd.DataFrame, layout: LayoutSpec) -> list[BankTransaction]:
    columns = layout.columns
    date_col = columns["date"]
    doc_col = columns["document_number"]
    debit_col = columns.get("debit")
    credit_col = columns.get("credit")
    bank_code_col = columns.get("bank_code")
    corr_col = (
        columns.get("combined_counterparty")
        or columns.get("counterparty_name")
        or columns.get("payment_purpose")
    )

    anchor_rows = [
        r for r in range(layout.data_start_row, len(grid)) if _row_text(grid, r, doc_col)
    ]

    transactions: list[BankTransaction] = []
    for i, anchor in enumerate(anchor_rows):
        block_end = anchor_rows[i + 1] if i + 1 < len(anchor_rows) else len(grid)

        transaction_date = parse_datetime_cell(grid.iat[anchor, date_col])
        if not transaction_date:
            continue
        for r in range(anchor + 1, block_end):
            if is_time_only(grid.iat[r, date_col]):
                transaction_date = merge_date_and_time(transaction_date, grid.iat[r, date_col])
                break

        document_number = _row_text(grid, anchor, doc_col)
        debit_amount = parse_amount(grid.iat[anchor, debit_col]) if debit_col is not None else 0.0
        credit_amount = parse_amount(grid.iat[anchor, credit_col]) if credit_col is not None else 0.0
        bank_code = _row_text(grid, anchor, bank_code_col)

        corr_texts = [_row_text(grid, r, corr_col) for r in range(anchor, block_end)]
        corr_texts = [t for t in corr_texts if t]
        anchor_corr = corr_texts[0] if corr_texts else ""
        labeled_bank_code, counterparty_account, _ = split_combined_counterparty(anchor_corr)
        bank_code = bank_code or labeled_bank_code

        continuation_texts = corr_texts[1:]
        counterparty_name = continuation_texts[0] if continuation_texts else ""
        payment_purpose = " ".join(continuation_texts[1:]) if len(continuation_texts) > 1 else ""

        transactions.append(
            BankTransaction(
                transaction_date=transaction_date,
                document_number=document_number,
                credit_amount=credit_amount,
                debit_amount=debit_amount,
                counterparty_name=counterparty_name,
                counterparty_account=counterparty_account,
                bank_code=bank_code,
                payment_purpose=payment_purpose,
            )
        )

    return transactions
