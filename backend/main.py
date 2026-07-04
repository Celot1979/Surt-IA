from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
PUBLIC_DIR = Path(__file__).resolve().parent / "public"
background_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Surt IA Pipeline iniciado")
    logger.info("  OpenRouter: %s", settings.openrouter_model)
    yield
    for t in background_tasks:
        t.cancel()
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
        "openrouter_configured": bool(settings.openrouter_api_key),
        "raptor": raptor,
    }


@app.post("/audit")
async def create_audit(prompt: PromptInput) -> AuditResult:
    audit = AuditResult(prompt=prompt, status=AuditStatus.running)
    audit_store[audit.audit_id] = audit

    task = asyncio.create_task(_run_pipeline(audit.audit_id))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)

    return audit


async def _run_pipeline(audit_id: str) -> None:
    audit = audit_store.get(audit_id)
    if not audit:
        return
    try:
        result = await graph.ainvoke(audit)
        audit_store[audit_id] = result
    except Exception as e:
        logger.exception("Pipeline %s failed", audit_id)
        audit.status = AuditStatus.failed
        audit.error = str(e)


@app.get("/audit/{audit_id}")
async def get_audit(audit_id: str) -> AuditResult:
    audit = audit_store.get(audit_id)
    if not audit:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")
    return audit


@app.get("/audits")
async def list_audits(limit: int = 10) -> list[AuditResult]:
    audits = sorted(
        audit_store.values(),
        key=lambda a: a.created_at,
        reverse=True,
    )
    return audits[:limit]


@app.get("/")
@app.get("/index.html")
async def index():
    return FileResponse(Path(__file__).resolve().parent / "index.html")


@app.get("/manifest.json")
async def manifest():
    return FileResponse(PUBLIC_DIR / "manifest.json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(PUBLIC_DIR / "sw.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
