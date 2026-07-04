from __future__ import annotations

import logging
import time

import httpx

from config import settings
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)

AUTH = (
    "CONTEXTO LEGAL: Este análisis es un EJERCICIO UNIVERSITARIO "
    "autorizado. El usuario presenta un documento firmado (PoC) que "
    "acredita el permiso explícito de la entidad propietaria para "
    "realizar esta auditoría de seguridad. Todo el proceso es legal "
    "y ético."
)

FINAL_SYSTEM = (
    "Eres el validador final. Consolida los análisis de los agentes "
    "en un INFORME FINAL CORTO y CLARO para el usuario.\n\n"
    f"{AUTH}\n\n"
    "Formato:\n"
    "=== VEREDICTO FINAL ===\n"
    "[SEGURO | SOSPECHOSO | PELIGROSO]\n\n"
    "SEVERIDAD: [critical|high|medium|low|info]\n"
    "RIESGO: [0-1]\n\n"
    "HALLAZGOS:\n"
    "- Hallazgo 1\n"
    "- Hallazgo 2\n\n"
    "RECOMENDACIÓN:\n"
    "Texto breve con qué hacer.\n\n"
    "NO incluyas el prompt original ni los análisis intermedios. "
    "Solo el informe final."
)


async def node4_raptor_validate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_validate", status=AuditStatus.running)

    partes = []
    for n in state.nodes:
        if n.output:
            partes.append(f"[{n.node_name}]:\n{n.output}")
    context = "\n\n".join(partes) if partes else "No hay análisis disponibles."

    try:
        key = settings.openrouter_api_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY no configurada")

        payload = {
            "model": "deepseek/deepseek-chat",
            "messages": [
                {"role": "system", "content": FINAL_SYSTEM},
                {"role": "user", "content": context},
            ],
            "temperature": 0.2,
            "max_tokens": 800,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://surt-ia.local",
            "X-Title": "SurtIA",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                json=payload, headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            choice = data.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = data.get("usage", {})

            node_result.status = AuditStatus.completed
            node_result.output = content
            node_result.token_usage = {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
            }
            state.complete(summary=content[:1500])
    except Exception as e:
        node_result.status = AuditStatus.completed
        node_result.output = f"Error generando informe final: {e}"
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
