import logging

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.models.bank_statement_schema import BankStatement
from app.services.bank_statement.engine import BankStatementParseError
from app.services.bank_statement.transform import parse_bank_statement
from app.services.file_parser import UnsupportedFileTypeError

router = APIRouter()
logger = logging.getLogger(__name__)

# User-facing message (Uzbek) shown whenever an uploaded file can't be turned into
# the required output — wrong layout, unsupported type, or unparseable content.
# Kept as one literal (not composed from exc details) so the wording stays exact.
TEMPLATE_REQUIRED_MESSAGE = "USHBU FAYLNI YUKLAB BO'LMADI, ILTIMOS BU FAYLNI SHABLON YORDAMIDA YUKLANG!"


@router.post("/bank-statement/transform", response_model=BankStatement)
async def transform_bank_statement(file: UploadFile = File(...)) -> BankStatement:
    settings = get_settings()

    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "FILE_TOO_LARGE",
                "message": f"File exceeds the {settings.max_upload_mb}MB upload limit.",
            },
        )

    try:
        return parse_bank_statement(file.filename or "", content)
    except UnsupportedFileTypeError as exc:
        logger.warning("Unsupported bank statement file type for %s: %s", file.filename, exc)
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "UNSUPPORTED_FILE_TYPE",
                "message": TEMPLATE_REQUIRED_MESSAGE,
            },
        ) from exc
    except BankStatementParseError as exc:
        logger.warning("Could not extract bank statement data from %s: %s", file.filename, exc)
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "BANK_STATEMENT_PARSE_FAILED",
                "message": TEMPLATE_REQUIRED_MESSAGE,
            },
        ) from exc
    except Exception as exc:
        logger.exception("Failed to parse bank statement %s", file.filename)
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "PARSE_FAILURE",
                "message": TEMPLATE_REQUIRED_MESSAGE,
            },
        ) from exc
