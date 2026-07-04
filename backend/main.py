from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from executor import healthcheck as raptor_healthcheck
from pipeline.graph import graph
from pipeline.models import AuditResult, AuditStatus, PromptInput

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

audit_store: dict[str, AuditResult] = {}
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "out"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Surt IA Pipeline iniciado")
    logger.info("  Gemini model: %s", settings.gemini_model)
    logger.info("  OpenRouter model: %s", settings.openrouter_model)
    logger.info("  Raptor dir: %s", settings.raptor_dir)
    logger.info("  Frontend: %s", FRONTEND_DIR if FRONTEND_DIR.exists() else "no built yet")
    yield
    logger.info("Surt IA Pipeline detenido")


app = FastAPI(
    title="Surt IA - Prompt Audit Pipeline",
    description="Pipeline multi-agente de auditoría de prompts con LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, Any]:
    raptor = raptor_healthcheck()
    return {
        "status": "ok",
        "gemini_configured": bool(settings.gemini_api_key),
        "openrouter_configured": bool(settings.openrouter_api_key),
        "raptor": raptor,
    }


@app.post("/audit", response_model=AuditResult)
async def create_audit(prompt: PromptInput) -> AuditResult:
    audit = AuditResult(prompt=prompt)
    audit_store[audit.audit_id] = audit

    try:
        final_state = await graph.ainvoke(audit)
        audit_store[audit.audit_id] = final_state
        return final_state
    except Exception as e:
        logger.exception("Error ejecutando pipeline de auditoría")
        audit.status = AuditStatus.failed
        audit.error = str(e)
        return audit


@app.get("/audit/{audit_id}", response_model=AuditResult)
async def get_audit(audit_id: str) -> AuditResult:
    audit = audit_store.get(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return audit


@app.get("/audits", response_model=list[AuditResult])
async def list_audits(limit: int = 10) -> list[AuditResult]:
    audits = sorted(
        audit_store.values(),
        key=lambda a: a.created_at,
        reverse=True,
    )
    return audits[:limit]


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
