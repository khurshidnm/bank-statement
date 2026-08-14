# CLAUDE.md

Project rules for working on the **Universal Data Normalizer & JSON Exporter**. See [README.md](README.md) for full architecture, API reference, and setup docs.

## Project Shape

- `backend/` — FastAPI service. All application code lives under `backend/app/`.
- `frontend/` — Next.js 14 App Router dashboard. All application code lives under `frontend/src/`.
- The two halves only communicate over HTTP (`POST /api/v1/transform`, `POST /api/v1/bank-statement/transform`). Do not import backend Python from the frontend or vice versa.
- `input/`/`output/` at the repo root (if present) are local dev fixtures for the bank statement engine — real bank exports and one reference target-JSON example. They contain real client financial data; never commit them as test fixtures or reference them from `backend/tests/` (which uses synthetic data instead).

## Backend Conventions

- `app/models/target_schema.py` is the single source of truth for the output shape (`TargetRecord`, `StandardizedDataset`). Changing the target schema means editing this file only — services and routes consume it, they don't redefine it.
- `app/services/file_parser.py` is pure data-plumbing: no AI calls, no FastAPI imports. It turns bytes into a `ParsedFile`/row dicts.
- `app/services/ai_mapper.py` is the only module allowed to call OpenAI/Anthropic. Route handlers call `map_rows_to_target_schema`; they never construct AI clients directly.
- `app/api/v1/transform.py` translates service-layer exceptions (`UnsupportedFileTypeError`, `EmptyFileError`, `AIMappingError`) into the `{"status": "error", "error_code": ..., "message": ...}` HTTP error contract documented in the README. Add new error codes there, not as raw `HTTPException` strings.
- New endpoints go under `app/api/v1/` and get included in `app/main.py`.
- Settings are read via `app/config.get_settings()` (env-backed `pydantic-settings`), never `os.environ` directly in business logic.
- Run tests with `cd backend && source venv/bin/activate && pytest tests/ -v`. AI calls must be mocked/monkeypatched in tests — never hit a live LLM API in the test suite.

### Bank statement engine (`app/services/bank_statement/`)

- This pipeline **never sends transaction amounts to an LLM** — figures are extracted deterministically via pandas so they can't be hallucinated. The one AI call in this pipeline (`ai_layout.py`) only describes *structure* (header row index, column→role mapping) as a fallback when `layout.detect_layout()` can't recognize a file; that structural spec is then executed by the same deterministic code path used for known formats. Keep it that way — don't add a code path that asks an LLM to transcribe rows here.
- Pipeline order (`transform.py`): `raw_loader.load_raw_grid` → `layout.detect_layout` (or `ai_layout.infer_layout_with_ai` on failure) → `adapters.is_multirow_layout` decides between `engine.extract_transactions` (one row per transaction) and `adapters.extract_multirow_transactions` (one transaction spread across several rows, e.g. date+amount on one row, name/purpose on the next) → `engine.build_statement`.
- `layout.py`'s header/column matching runs everything through `normalize()` (lowercases, strips whitespace/apostrophes, folds ё→е, collapses doubled letters) on **both** the header text and the phrase constants — real bank exports have typos like `кореспондента` (missing a letter) or homoglyphs like a Latin `C` in `Cчет/ИНН`. When adding a new phrase to `_ROLE_PHRASES_RAW`, write it with correct spelling; normalization handles the drift. Order matters: more specific/longer phrases must come before shorter ones they contain as a substring (e.g. `наименование счета` before bare `счет`, `vakil hisob raqam nomi` before `vakil hisob raqam`) — checked in list order, first match wins.
- The bare "Счет"/"Наименование" ambiguity (same header can mean the statement owner's own account or the counterparty's, depending on the bank) is resolved by sampling data values against the account number found in the preamble, not by per-bank branching — see `_resolve_ambiguous_columns`. Don't special-case a bank name in `layout.py`; if a new file needs bank-specific handling, that belongs in `adapters.py` (see `is_multirow_layout`/`extract_multirow_transactions` for the pattern), gated on a structural signature, not a filename.
- Real export quirks already handled, worth knowing before "fixing" something that looks broken: some templates put metadata (account number, opening balance) *after* the header row rather than before (`detect_layout` scans forward for the first row with a parseable date to find where data actually starts); some `.xls` files are actually HTML tables (`raw_loader._looks_like_html`) whose account preamble lives in a separate `<table>` from the transaction grid (hence `pd.concat`, not "pick the biggest table"); amount cells may be plain floats or locale-formatted text with either `,` or `.` as the decimal separator (`parsing_utils.parse_amount`).

## Frontend Conventions

- `src/lib/api.ts` is the only module that talks to the backend. Components call `transformFile()`; they don't call `axios`/`fetch` directly.
- Client components that use hooks or browser APIs need `"use client"` at the top (see `FileDropzone.tsx`, `JsonViewer.tsx`, `page.tsx`).
- Styling is Tailwind utility classes only — no CSS modules, no styled-components. Shared design tokens (colors) live in `tailwind.config.ts`.
- Keep `FileDropzone`, `JsonViewer`, and `Header` presentational and composed from `page.tsx`; page-level state (upload status, progress, result, error) stays in `page.tsx`.

## Making Changes

- If you change `TargetRecord` fields in the backend, update the `TargetRecord` interface in `frontend/src/lib/api.ts` to match — the two are not type-shared and must be kept in sync by hand.
- If you add a new supported file extension, update `SUPPORTED_EXTENSIONS` in `file_parser.py` **and** the `ACCEPTED_MIME_TYPES` map in `FileDropzone.tsx`.
- Prefer extending the existing `TargetRecord`/`StandardizedDataset` Pydantic models over inventing a parallel schema — see the "Customizing the Target Schema" section of the README for the intended workflow.

## Example Prompts

- `"Read CLAUDE.md and implement backend/app/services/file_parser.py to support multi-sheet Excel files with Pandas."`
- `"Implement backend/app/services/ai_mapper.py using OpenAI response_format with the StandardizedDataset Pydantic model."`
- `"Construct frontend/src/components/FileDropzone.tsx using React Dropzone with progress state indicators."`
