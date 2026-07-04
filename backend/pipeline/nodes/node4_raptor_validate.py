from __future__ import annotations

import logging
import time

from executor import run_raptor_agentic
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)

FINAL_PROMPT = (
    "Eres el validador final del pipeline. Todos los agentes anteriores han emitido su análisis.\n"
    "Genera un INFORME FINAL DE AUDITORÍA que consolide y resuelva discrepancias.\n\n"
    "Formato requerido:\n"
    "=== VEREDICTO FINAL ===\n"
    "[CRITICAL | HIGH | MEDIUM | LOW | INFO] - Breve descripción\n\n"
    "=== HALLAZGOS CONSOLIDADOS ===\n"
    "- Hallazgo 1 (Severidad) - Descripción\n"
    "- Hallazgo 2 (Severidad) - Descripción\n\n"
    "=== ANÁLISIS DE CONSENSO ===\n"
    "Puntos de acuerdo entre agentes, discrepancias resueltas, y conclusión.\n\n"
    "=== RECOMENDACIONES ===\n"
    "- Recomendación 1\n"
    "- Recomendación 2\n"
)


def _build_context(state: AuditResult) -> str:
    parts = [FINAL_PROMPT, "=== HISTORIAL COMPLETO DEL PIPELINE ==="]
    for n in state.nodes:
        parts.append(f"\n--- [{n.node_name}] (estado: {n.status.value}) ---")
        if n.output:
            parts.append(n.output[:1000])
        if n.error:
            parts.append(f"ERROR: {n.error}")
    parts.append("\n=== GENERA EL INFORME FINAL ===")
    return "\n".join(parts)


async def _call_final_summary(context: str) -> dict:
    import httpx
    key = settings.openrouter_api_key
    if not key:
        return {"success": False, "error": "OPENROUTER_API_KEY no configurada", "content": None}

    url = f"{settings.openrouter_base_url}/chat/completions"
    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": context}],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://surt-ia.local",
        "X-Title": "SurtIA",
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            usage = data.get("usage", {})
            return {
                "success": True,
                "content": choice.get("message", {}).get("content", ""),
                "token_usage": {
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            }
    except Exception as e:
        return {"success": False, "error": str(e), "content": None}


async def node4_raptor_validate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_validate", status=AuditStatus.running)

    target_path = state.prompt.target_path

    if target_path:
        logger.info("Ejecutando Raptor agentic sobre %s", target_path)
        try:
            result = run_raptor_agentic(target_path, timeout=120)
            if result.get("error"):
                node_result.error = result["error"]
        except Exception:
            pass

    context = _build_context(state)
    try:
        summary = await _call_final_summary(context)
        if summary["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = summary["content"]
            node_result.token_usage = summary.get("token_usage", {})
            state.complete(summary=summary["content"][:2000])
        else:
            node_result.status = AuditStatus.completed
            node_result.output = context
            node_result.error = f"Resumen LLM no disponible: {summary.get('error')}"
    except Exception as e:
        node_result.status = AuditStatus.completed
        node_result.output = context
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
