from typing import List, Optional

from pydantic import BaseModel, Field


class TargetRecord(BaseModel):
    """A single normalized record in the target output schema."""

    record_id: str = Field(..., description="Unique record identifier or generated hash")
    customer_name: str = Field(..., description="Cleaned full customer or company name")
    email: str = Field(..., description="Normalized lowercase email address")
    transaction_amount: float = Field(..., description="Numeric transaction amount parsed from string or currency")
    transaction_date: str = Field(..., description="Standard ISO date string YYYY-MM-DD")
    status: Optional[str] = Field("completed", description="Status string (completed, pending, cancelled)")


class StandardizedDataset(BaseModel):
    records: List[TargetRecord]


class TransformResponse(BaseModel):
    status: str = "success"
    filename: str
    total_records_processed: int
    data: List[TargetRecord]


class ErrorResponse(BaseModel):
    status: str = "error"
    error_code: str
    message: str
