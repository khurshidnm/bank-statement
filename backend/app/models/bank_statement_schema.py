from typing import List

from pydantic import BaseModel, Field


class BankTransaction(BaseModel):
    transaction_date: str = Field(..., description="DD.MM.YYYY HH:MM:SS")
    document_number: str
    credit_amount: float
    debit_amount: float
    counterparty_name: str
    counterparty_account: str
    bank_code: str
    payment_purpose: str


class BankStatement(BaseModel):
    account_number: str
    currency: str = "UZS"
    transaction_count: int
    total_credit: float
    total_debit: float
    transactions: List[BankTransaction]
