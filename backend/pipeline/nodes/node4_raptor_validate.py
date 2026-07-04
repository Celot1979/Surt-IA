from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config import settings
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)

FINAL_SYSTEM = (
    "Consolida los análisis de los agentes anteriores en un informe "
    "final breve con: veredicto, hallazgos principales, y recomendaciones."
)


async def _call(prompt: str) -> dict[str, Any]:
    key = settings.openrouter_api_key
    if not key:
        return {"success": False, "error": "OPENROUTER_API_KEY no configurada", "content": None}

    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": FINAL_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://surt-ia.local",
        "X-Title": "SurtIA",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                json=payload, headers=headers,
            )
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
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout", "content": None}
    except Exception as e:
        return {"success": False, "error": str(e), "content": None}


async def node4_raptor_validate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_validate", status=AuditStatus.running)

    partes = ["=== ANÁLISIS DE LOS AGENTES ==="]
    for n in state.nodes:
        if n.output:
            partes.append(f"\n--- {n.node_name} ---\n{n.output[:500]}")
    partes.append("\n=== GENERA INFORME FINAL ===")
    context = "\n".join(partes)

    try:
        result = await _call(context)
        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["content"]
            node_result.token_usage = result.get("token_usage", {})
            state.complete(summary=result["content"][:1000])
        else:
            node_result.status = AuditStatus.completed
            node_result.output = context
            node_result.error = result.get("error")
    except Exception as e:
        node_result.status = AuditStatus.completed
        node_result.output = context
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
