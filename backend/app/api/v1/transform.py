import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.config import get_settings
from app.models.target_schema import TransformResponse
from app.services.ai_mapper import AIMappingError, map_rows_to_target_schema
from app.services.file_parser import (
    EmptyFileError,
    UnsupportedFileTypeError,
    parse_file,
    sample_rows,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/transform", response_model=TransformResponse)
async def transform_file(file: UploadFile = File(...)) -> TransformResponse:
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
        parsed = parse_file(file.filename or "", content)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "UNSUPPORTED_FILE_TYPE",
                "message": str(exc),
            },
        ) from exc
    except EmptyFileError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "EMPTY_FILE",
                "message": str(exc),
            },
        ) from exc
    except Exception as exc:  # malformed workbook/csv/json content
        logger.exception("Failed to parse uploaded file %s", file.filename)
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "PARSE_FAILURE",
                "message": f"Could not parse the uploaded file: {exc}",
            },
        ) from exc

    rows = sample_rows(parsed, max_rows=settings.sample_rows)

    try:
        dataset = map_rows_to_target_schema(rows, parsed.source_columns)
    except AIMappingError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "status": "error",
                "error_code": "AI_MAPPING_FAILED",
                "message": str(exc),
            },
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "status": "error",
                "error_code": "SCHEMA_VALIDATION_FAILED",
                "message": str(exc),
            },
        ) from exc

    return TransformResponse(
        filename=file.filename or "unknown",
        total_records_processed=len(dataset.records),
        data=dataset.records,
    )
