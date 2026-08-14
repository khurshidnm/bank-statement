from app.models.bank_statement_schema import BankStatement
from app.services.bank_statement.adapters import extract_multirow_transactions, is_multirow_layout
from app.services.bank_statement.ai_layout import infer_layout_with_ai
from app.services.bank_statement.engine import BankStatementParseError, build_statement, extract_transactions
from app.services.bank_statement.layout import detect_layout
from app.services.bank_statement.raw_loader import load_raw_grid


def parse_bank_statement(filename: str, content: bytes) -> BankStatement:
    grid = load_raw_grid(filename, content)

    layout = detect_layout(grid)
    if layout is None:
        layout = infer_layout_with_ai(grid)
    if layout is None:
        raise BankStatementParseError(
            "Could not recognize this file's layout as a bank statement. "
            "It may use a format this service hasn't seen before."
        )

    if layout.ai_multirow or is_multirow_layout(grid, layout):
        transactions = extract_multirow_transactions(grid, layout)
    else:
        transactions = extract_transactions(grid, layout)

    return build_statement(layout, transactions)
