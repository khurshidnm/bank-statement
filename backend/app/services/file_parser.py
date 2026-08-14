import io
import json
from dataclasses import dataclass

import pandas as pd

SUPPORTED_EXTENSIONS = {"xlsx", "xls", "csv", "json"}


class UnsupportedFileTypeError(Exception):
    pass


class EmptyFileError(Exception):
    pass


@dataclass
class ParsedFile:
    """Result of parsing an uploaded file into a tabular DataFrame."""

    dataframe: pd.DataFrame
    sheet_name: str | None
    source_columns: list[str]
    row_count: int


def get_extension(filename: str) -> str:
    if "." not in filename:
        raise UnsupportedFileTypeError("File has no extension.")
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Only {', '.join(sorted(SUPPORTED_EXTENSIONS))} files are supported."
        )
    return ext


def parse_file(filename: str, content: bytes) -> ParsedFile:
    """Detect the file type from its extension and load it into a DataFrame."""
    ext = get_extension(filename)
    buffer = io.BytesIO(content)

    if ext in ("xlsx", "xls"):
        df = _parse_excel(buffer)
    elif ext == "csv":
        df = _parse_csv(buffer)
    else:
        df = _parse_json(buffer)

    if df.empty:
        raise EmptyFileError("The uploaded file contains no rows of data.")

    df = df.dropna(axis="columns", how="all")
    df.columns = [str(c).strip() for c in df.columns]

    return ParsedFile(
        dataframe=df,
        sheet_name=None,
        source_columns=list(df.columns),
        row_count=len(df),
    )


def _parse_excel(buffer: io.BytesIO) -> pd.DataFrame:
    workbook = pd.read_excel(buffer, sheet_name=None, engine="openpyxl")
    # Use the first non-empty sheet when a workbook has multiple sheets.
    for name, sheet_df in workbook.items():
        if not sheet_df.dropna(how="all").empty:
            return sheet_df
    return next(iter(workbook.values()))


def _parse_csv(buffer: io.BytesIO) -> pd.DataFrame:
    return pd.read_csv(buffer, sep=None, engine="python")


def _parse_json(buffer: io.BytesIO) -> pd.DataFrame:
    raw = json.loads(buffer.getvalue().decode("utf-8"))
    if isinstance(raw, dict):
        # Support {"data": [...]}-style wrappers as well as raw record dicts.
        for value in raw.values():
            if isinstance(value, list):
                raw = value
                break
        else:
            raw = [raw]
    return pd.json_normalize(raw)


def sample_rows(parsed: ParsedFile, max_rows: int = 15) -> list[dict]:
    """Extract a representative sample of rows for LLM schema inference."""
    sample_df = parsed.dataframe.head(max_rows)
    sample_df = sample_df.astype(object).where(pd.notnull(sample_df), None)
    return sample_df.to_dict(orient="records")


def full_rows(parsed: ParsedFile) -> list[dict]:
    """Convert the entire parsed dataframe to a list of dicts for downstream mapping."""
    df = parsed.dataframe.astype(object).where(pd.notnull(parsed.dataframe), None)
    return df.to_dict(orient="records")
