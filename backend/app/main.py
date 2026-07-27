from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    advances,
    auth,
    company_settings,
    customers,
    invoices,
    materials,
    payments,
    reports,
    users,
)
from app.core.bootstrap import bootstrap_database
from app.core.config import settings
from app.core.database import SessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        bootstrap_database(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Billing, sales, partial payment, advance, ledger, and reporting API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(customers.router)
app.include_router(materials.router)
app.include_router(invoices.router)
app.include_router(payments.router)
app.include_router(advances.router)
app.include_router(reports.router)
app.include_router(company_settings.router)
app.include_router(users.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
