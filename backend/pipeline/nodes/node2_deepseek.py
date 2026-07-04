from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config import settings
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)

SYSTEM = (
    "Eres un segundo revisor de prompts. Recibes el prompt original "
    "y el análisis del primer agente. Revisa si estás de acuerdo, "
    "complementa hallazgos, ajusta severidad. Responde breve."
)


async def _call(prompt: str) -> dict[str, Any]:
    key = settings.openrouter_api_key
    if not key:
        return {"success": False, "error": "OPENROUTER_API_KEY no configurada", "content": None}

    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM},
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


async def node2_deepseek(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="deepseek", status=AuditStatus.running)

    gemini_output = None
    for n in state.nodes:
        if n.node_name == "gemini" and n.output:
            gemini_output = n.output

    ctx = f"Prompt: {state.prompt.content}\n"
    ctx += f"Análisis de Gemini:\n{gemini_output or '(no disponible)'}\n"
    ctx += "Tu revisión:"

    try:
        result = await _call(ctx)
        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["content"]
            node_result.token_usage = result.get("token_usage", {})
        else:
            node_result.status = AuditStatus.failed
            node_result.error = result.get("error")
    except Exception as e:
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
