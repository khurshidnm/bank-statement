from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.bank_statement import router as bank_statement_router
from app.api.v1.transform import router as transform_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Universal Data Normalizer & JSON Exporter",
    description="Normalizes inconsistent Excel/CSV/JSON files into a standardized target JSON schema via LLM-driven mapping.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transform_router, prefix="/api/v1", tags=["transform"])
app.include_router(bank_statement_router, prefix="/api/v1", tags=["bank-statement"])


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
