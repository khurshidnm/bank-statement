import io
import re

import pandas as pd

from app.services.file_parser import UnsupportedFileTypeError

_HTML_SNIFF_RE = re.compile(rb"^\s*<(html|!doctype)|<table", re.IGNORECASE)
_CHARSET_RE = re.compile(rb'charset=["\']?([\w\-]+)', re.IGNORECASE)


def _looks_like_html(content: bytes) -> bool:
    return bool(_HTML_SNIFF_RE.search(content[:4096]))


def _html_encoding(content: bytes) -> str:
    match = _CHARSET_RE.search(content[:4096])
    return match.group(1).decode("ascii", errors="ignore") if match else "utf-8"


def load_raw_grid(filename: str, content: bytes) -> pd.DataFrame:
    """Load a spreadsheet into a raw, header-less grid preserving native cell types
    (dates as Timestamps, numbers as floats). Some banking portals export report
    files with an .xls extension that are actually HTML tables — those are detected
    and parsed via read_html instead of the Excel engines."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if _looks_like_html(content):
        encoding = _html_encoding(content)
        try:
            html_text = content.decode(encoding, errors="replace")
        except LookupError:
            html_text = content.decode("cp1251", errors="replace")
        tables = pd.read_html(io.StringIO(html_text), header=None, thousands=None)
        if not tables:
            raise ValueError("No HTML tables found in file content.")
        # Banking portals often split the account preamble and the transaction
        # grid into separate <table> elements; stack them so preamble metadata
        # (account number, etc.) isn't lost when only the largest table is kept.
        return pd.concat(tables, ignore_index=True, sort=False)

    if ext == "xlsx":
        return pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="openpyxl")
    if ext == "xls":
        return pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="xlrd")

    raise UnsupportedFileTypeError(f"Unsupported bank statement file type: .{ext or '?'}")
