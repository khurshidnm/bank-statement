# 🚀 Universal Data Normalizer & JSON Exporter

An AI-powered online service that accepts inconsistent, unstructured, or varied data files (**Excel `.xlsx`/`.xls`**, **CSV**, and **JSON**) with arbitrary column names or cell arrangements, automatically normalizes and maps the fields using LLM-driven schema mapping, and exports a standardized, validated **Target JSON** file.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Data Flow & Processing Lifecycle](#data-flow--processing-lifecycle)
- [Tech Stack](#tech-stack)
- [Project Directory Structure](#project-directory-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [1. Backend Setup (FastAPI)](#1-backend-setup-fastapi)
  - [2. Frontend Setup (Next.js)](#2-frontend-setup-nextjs)
- [API Reference](#api-reference)
- [Customizing the Target Schema](#customizing-the-target-schema)
- [Claude Code Integration Guide](#claude-code-integration-guide)
- [Environment Variables](#environment-variables)
- [Deployment](#deployment)
- [License](#license)

---

## 🔍 Overview

In real-world business workflows, incoming data files from different clients or vendors rarely follow the same format. Column headers vary (`Cust_Name`, `Full Name`, `Client`), dates are formatted differently (`DD/MM/YYYY`, `MM-DD-YY`, Unix timestamps), and cell layouts can be messy.

**Universal Data Normalizer** solves this problem by using **LLM Structured Outputs (OpenAI GPT-4o-mini / Claude 3.5 Sonnet)** combined with **Pandas / OpenPyXL** parsing to automatically infer, clean, type-cast, and map unpredictable incoming spreadsheets and documents directly into a strict, predefined target JSON schema.

---

## ✨ Key Features

- **Multi-Format Ingestion:** Native parsing support for `.xlsx`, `.xls`, `.csv`, and `.json` files up to 25MB.
- **AI-Powered Field Mapping:** Semantic column matching that understands messy or variant header names (e.g., mapping `Txn_Val`, `Amount Paid`, or `Sum$` to `total_amount`).
- **Data Cleansing & Type Standardization:**
  - Standardizes dates to ISO 8601 (`YYYY-MM-DD`).
  - Cleans currencies and strings (e.g., `$1,250.00` $\rightarrow$ `1250.00`).
  - Strips whitespace, normalizes email addresses to lowercase, and reformats numeric IDs.
- **Strict Schema Enforcement:** Leverages **Pydantic v2** and **OpenAI Structured Outputs** (`response_format`) to guarantee 0% output schema deviation.
- **Efficient Token Usage:** Extracts an optimal 15-row representative sample for schema inference rather than sending multi-megabyte raw files to the LLM.
- **Modern Interactive Dashboard:** Drag-and-drop file uploader, real-time transformation status, side-by-side preview diff, formatted JSON viewer, and one-click `.json` file download.

---

## 📐 System Architecture

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                   CLIENT / FRONTEND                               │
│                         (Next.js 14 + React Dropzone + Tailwind)                  │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │  Multipart Form Data (Upload File)
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                   FASTAPI BACKEND                                 │
│                                                                                   │
│  ┌───────────────────────┐    ┌────────────────────────┐    ┌──────────────────┐ │
│  │ File Reader Service   │───>│ Structural Sampler     │───>│ OpenAI / Claude  │ │
│  │ (Pandas / OpenPyXL)   │    │ (Top 15 Rows + Schema) │    │ Structured API   │ │
│  └───────────────────────┘    └────────────────────────┘    └─────────┬────────┘ │
│                                                                       │          │
│  ┌───────────────────────┐    ┌────────────────────────┐              │          │
│  │ Standardized Output   │<───│ Pydantic Validation    │<─────────────┘          │
│  │ Generator (.json)     │    │ (Strict Schema Rules)  │                         │
│  └───────────────────────┘    └────────────────────────┘                         │
└─────────────────────────────────────────┬─────────────────────────────────────────┘
                                          │  JSON Payload
                                          ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                                 CLIENT DASHBOARD                                  │
│                 (JSON Code Previewer + Copy & Single-Click Download)              │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow & Processing Lifecycle

1. **File Upload:** The user drops an Excel, CSV, or JSON file into the web UI.
2. **Parsing & Inspection:** The FastAPI backend inspects the file, detects sheet names/delimiter options, and loads the data using `pandas`.
3. **Sampling:** A 15-row representative preview block is generated.
4. **LLM Inference:** The preview block along with instructions is passed to the AI engine (GPT-4o-mini with Pydantic schema constraints).
5. **Normalizing & Casting:** The AI maps fields semantically, normalizes values (dates, numbers, strings), and returns the mapped structured records.
6. **Validation:** Pydantic checks all records against target types (`str`, `float`, `int`, etc.).
7. **Response:** The validated JSON array is sent back to the client UI for display and download.

---

## 🛠️ Tech Stack

### Backend
- **Framework:** Python 3.11+, FastAPI, Uvicorn
- **Data Engine:** Pandas, OpenPyXL, NumPy
- **Validation:** Pydantic v2
- **AI Integration:** OpenAI Python SDK (`openai`), Anthropic SDK (`anthropic`)

### Frontend
- **Framework:** Next.js 14+ (App Router, React 18, TypeScript)
- **Styling:** Tailwind CSS, Shadcn UI, Lucide Icons
- **Upload & State:** React Dropzone, Axios
- **Code Viewer:** `@monaco-editor/react` or `react-syntax-highlighter`

---

## 📁 Project Directory Structure

```
universal-json-transformer/
├── CLAUDE.md                   # System rules and instructions for Claude Code
├── README.md                   # Complete project documentation
├── LICENSE                     # MIT License
├── docker-compose.yml          # Runs backend + frontend together (VPS deployment)
├── deploy/
│   └── nginx.conf.example      # Reverse proxy + HTTPS config template for a VPS
│
├── backend/                    # FastAPI Microservice
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI App entrypoint & CORS configuration
│   │   ├── config.py           # Pydantic settings & env loader
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── transform.py       # POST /api/v1/transform endpoint
│   │   │       └── bank_statement.py  # POST /api/v1/bank-statement/transform endpoint
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── target_schema.py         # Target Pydantic output model definition
│   │   │   └── bank_statement_schema.py # Bank statement Pydantic output model
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── file_parser.py  # Pandas / OpenPyXL reading & sampling engine
│   │       ├── ai_mapper.py    # OpenAI Structured Outputs client wrapper
│   │       └── bank_statement/ # Deterministic bank statement parsing engine
│   │           ├── raw_loader.py    # File/HTML loading (incl. HTML-as-.xls exports)
│   │           ├── layout.py        # Header row + column-role detection
│   │           ├── engine.py        # Single-row transaction extraction
│   │           ├── adapters.py      # Multi-row transaction layout handling
│   │           ├── ai_layout.py     # AI-assisted structure inference fallback
│   │           ├── parsing_utils.py # Amount/date parsing, regex helpers
│   │           └── transform.py     # Orchestrator: load -> detect -> extract
│   ├── tests/
│   │   ├── test_parser.py      # Unit tests for multi-format file parser
│   │   ├── test_transformation.py
│   │   ├── test_bank_statement_parsing_utils.py
│   │   └── test_bank_statement_engine.py
│   ├── Dockerfile
│   ├── .env.example
│   └── requirements.txt
│
└── frontend/                   # Next.js Web Dashboard
    ├── src/
    │   ├── app/
    │   │   ├── layout.tsx
    │   │   ├── page.tsx        # Main application dashboard page
    │   │   └── globals.css
    │   ├── components/
    │   │   ├── FileDropzone.tsx# Drag-and-drop file upload UI
    │   │   ├── JsonViewer.tsx  # Interactive syntax-highlighted JSON viewer
    │   │   └── Header.tsx
    │   └── lib/
    │       └── api.ts          # Axios API communication methods
    ├── public/
    ├── Dockerfile
    ├── .env.local.example
    ├── package.json
    └── tsconfig.json
```

---

## 🚀 Getting Started

### Prerequisites
- **Python:** Version 3.11 or higher
- **Node.js:** Version 18.0 or higher
- **Package Manager:** `npm` or `pnpm`
- **OpenAI API Key:** Required for structured output transformation

---

### 1. Backend Setup (FastAPI)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On macOS/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   cp .env.example .env
   ```
   Add your `OPENAI_API_KEY` to `.env`:
   ```env
   OPENAI_API_KEY=sk-proj-your-openai-api-key-here
   PORT=8000
   ```

5. Run the development server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *The API documentation will be available at `http://localhost:8000/docs`.*

---

### 2. Frontend Setup (Next.js)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install npm dependencies:
   ```bash
   npm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.local.example .env.local
   ```
   Ensure `.env.local` points to your local backend:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   *Access the web dashboard at `http://localhost:3000`.*

---

## 📡 API Reference

### Transform File to Target JSON

`POST /api/v1/transform`

Converts uploaded `.xlsx`, `.xls`, `.csv`, or `.json` file to the standardized JSON output schema.

#### Request Headers
`Content-Type: multipart/form-data`

#### Request Body
- `file` *(binary file, required)*: Spreadsheet or JSON document.

#### Example Curl Request
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/transform' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@sample_sales_data.xlsx'
```

#### Success Response (200 OK)
```json
{
  "status": "success",
  "filename": "sample_sales_data.xlsx",
  "total_records_processed": 3,
  "data": [
    {
      "record_id": "REC-001",
      "customer_name": "Acme Corporation",
      "email": "contact@acme.com",
      "transaction_amount": 1450.75,
      "transaction_date": "2026-08-10",
      "status": "completed"
    },
    {
      "record_id": "REC-002",
      "customer_name": "Globex Industries",
      "email": "billing@globex.org",
      "transaction_amount": 890.00,
      "transaction_date": "2026-08-11",
      "status": "pending"
    }
  ]
}
```

#### Error Response (422 Unprocessable Entity)
```json
{
  "status": "error",
  "error_code": "UNSUPPORTED_FILE_TYPE",
  "message": "Only .xlsx, .xls, .csv, and .json files are supported."
}
```

---

### Transform Bank Statement to Standardized JSON

`POST /api/v1/bank-statement/transform`

A specialized sibling of the generic transform endpoint, purpose-built for bank account statement exports (`.xlsx`/`.xls`, including HTML-formatted files with an `.xls` extension, as some banking portals produce). Unlike the generic endpoint, this one **never sends transaction figures to an LLM**. It uses a deterministic engine — header/column detection via a bilingual (Russian/Uzbek) keyword vocabulary, own-vs-counterparty account disambiguation by sampling data against the statement's own account number, and dedicated handling for combined "account/inn/name" cells and multi-row transaction layouts — to extract amounts, dates, and parties programmatically. An LLM is only consulted as a fallback when the deterministic layout detector can't recognize a file at all, and even then it's asked only to describe the *structure* (which row is the header, which column is which field) — never to transcribe the numbers themselves — so a brand-new bank export format can be picked up without hardcoding a new adapter, while figures stay exact.

See `backend/app/services/bank_statement/` for the implementation: `raw_loader.py` (file/HTML loading), `layout.py` (header + column-role detection), `engine.py` (single-row extraction), `adapters.py` (multi-row transaction layouts), `ai_layout.py` (AI-assisted structure inference fallback), and `transform.py` (orchestrator).

#### Request Body
- `file` *(binary file, required)*: Bank statement spreadsheet (`.xlsx` or `.xls`).

#### Example Curl Request
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/bank-statement/transform' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@statement.xlsx'
```

#### Success Response (200 OK)
```json
{
  "account_number": "20208000505569397001",
  "currency": "UZS",
  "transaction_count": 115,
  "total_credit": 1107337553.86,
  "total_debit": 1100852015.99,
  "transactions": [
    {
      "transaction_date": "01.08.2025 16:07:00",
      "document_number": "261200",
      "credit_amount": 0,
      "debit_amount": 300,
      "counterparty_name": "16401000905569397001/309882946/TOShKENT Sh. AT \"ALOQABANK\" BOSh OFISI",
      "counterparty_account": "16401000905569397001",
      "bank_code": "00401",
      "payment_purpose": "00668~За перевод электронных платежей..."
    }
  ]
}
```

#### Error Response (422 Unprocessable Entity)

Whenever an uploaded file can't be turned into the required output — unrecognized layout, wrong file type, or unparseable content — `message` is the fixed, user-facing Uzbek string below (shown as-is to end users on the upload UI); `error_code` stays machine-readable for logs/support. A separate `FILE_TOO_LARGE` error (over the `MAX_UPLOAD_MB` limit) keeps its own descriptive message instead, since "use the template" isn't the fix for that one.

```json
{
  "status": "error",
  "error_code": "BANK_STATEMENT_PARSE_FAILED",
  "message": "USHBU FAYLNI YUKLAB BO'LMADI, ILTIMOS BU FAYLNI SHABLON YORDAMIDA YUKLANG!"
}
```

---

## 🎯 Customizing the Target Schema

To change the single target output JSON structure to match your exact business requirements, modify `backend/app/models/target_schema.py`:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class TargetRecord(BaseModel):
    record_id: str = Field(..., description="Unique record identifier or generated hash")
    customer_name: str = Field(..., description="Cleaned full customer or company name")
    email: str = Field(..., description="Normalized lowercase email address")
    transaction_amount: float = Field(..., description="Numeric transaction amount parsed from string or currency")
    transaction_date: str = Field(..., description="Standard ISO date string YYYY-MM-DD")
    status: Optional[str] = Field("completed", description="Status string (completed, pending, cancelled)")

class StandardizedDataset(BaseModel):
    records: List[TargetRecord]
```

---

## 🤖 Claude Code Integration Guide

When developing this project inside **VS Code** using **Claude Code**, place the provided `CLAUDE.md` in your project root. 

You can ask Claude Code to perform specific generation tasks step-by-step:

- **Generate Backend Core:**  
  > `"Read CLAUDE.md and implement backend/app/services/file_parser.py to support multi-sheet Excel files with Pandas."`

- **Build AI Transformation Engine:**  
  > `"Implement backend/app/services/ai_mapper.py using OpenAI response_format with the StandardizedDataset Pydantic model."`

- **Build Dropzone UI:**  
  > `"Construct frontend/src/components/FileDropzone.tsx using React Dropzone with progress state indicators."`

---

## 🔐 Environment Variables

| Variable | Scope | Description | Default |
| :--- | :--- | :--- | :--- |
| `OPENAI_API_KEY` | Backend | OpenAI API Key for structured output LLM inference. | *Required* |
| `ANTHROPIC_API_KEY` | Backend | Anthropic (Claude) API key; used when `AI_PROVIDER=anthropic`. | *Optional* |
| `AI_PROVIDER` | Backend | Which LLM provider to use (`openai` or `anthropic`) across both the generic normalizer and the bank statement AI-layout fallback. | `openai` |
| `PORT` | Backend | Port on which FastAPI server runs. | `8000` |
| `CORS_ORIGINS` | Backend | Allowed CORS origins for frontend access. | `http://localhost:3000` |
| `MAX_UPLOAD_MB` | Backend | Maximum upload size accepted by both transform endpoints. | `25` |
| `SAMPLE_ROWS` | Backend | Row sample size sent to the LLM by the generic normalizer's schema-inference step. | `15` |
| `NEXT_PUBLIC_API_URL` | Frontend | URL of the backend FastAPI service. | `http://localhost:8000` |

---

## ☁️ Deployment

### Deployment on a VPS (e.g. Hostinger)

This is the recommended path for a self-managed VPS. `docker-compose.yml` builds and runs both services (backend on `127.0.0.1:8000`, frontend on `127.0.0.1:3000`, both loopback-only); Nginx on the host handles the public domain and HTTPS.

1. **Point your domain(s) at the VPS.** Add A records for your frontend domain (e.g. `your-domain.com`) and, if you want the API on its own subdomain, `api.your-domain.com`, both pointing to the VPS's IP.

2. **SSH in and install prerequisites** (Ubuntu/Debian shown; Hostinger VPS plans default to this):
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git
   sudo systemctl enable --now docker
   ```

3. **Clone your repository:**
   ```bash
   git clone https://github.com/<your-username>/<your-repo>.git
   cd <your-repo>
   ```

4. **Set up environment files** (these are gitignored — they never come from the repo):
   ```bash
   cp backend/.env.example backend/.env
   # edit backend/.env: set OPENAI_API_KEY (and/or ANTHROPIC_API_KEY + AI_PROVIDER),
   # and set CORS_ORIGINS to https://your-domain.com
   ```
   `NEXT_PUBLIC_API_URL` and `CORS_ORIGINS` are read from your shell environment by `docker-compose.yml` — export them before starting, or add them to a root `.env` file (also gitignored) that Docker Compose loads automatically:
   ```bash
   cat > .env <<'EOF'
   NEXT_PUBLIC_API_URL=https://api.your-domain.com
   CORS_ORIGINS=https://your-domain.com
   EOF
   ```

5. **Build and start both services:**
   ```bash
   sudo docker compose up --build -d
   sudo docker compose ps   # confirm both containers are healthy
   ```

6. **Configure Nginx as the reverse proxy.** A ready-to-adapt config is at `deploy/nginx.conf.example` — copy it in, swap in your real domain names, then enable it:
   ```bash
   sudo cp deploy/nginx.conf.example /etc/nginx/sites-available/your-domain
   sudo ln -s /etc/nginx/sites-available/your-domain /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   ```

7. **Enable HTTPS:**
   ```bash
   sudo certbot --nginx -d your-domain.com -d api.your-domain.com
   ```

8. **Deploying updates** after pushing new commits:
   ```bash
   git pull && sudo docker compose up --build -d
   ```

> **Note:** never commit real `.env` files or the `input/`/`output/` sample-data folders — they're excluded in `.gitignore` on purpose. Copy `.env.example` files on the server and fill in real secrets there instead.

### Deployment on Railway

1. Push your repository to GitHub.
2. Create a new project in **Railway** and link your GitHub repository.
3. Deploy two services:
   - **Backend Service:** Set root directory to `/backend`. Add `OPENAI_API_KEY` in environment variables.
   - **Frontend Service:** Set root directory to `/frontend`. Set `NEXT_PUBLIC_API_URL` to your Railway Backend public domain.

---

## 📄 License

This project is licensed under the **MIT License**. See the `LICENSE` file for details.
