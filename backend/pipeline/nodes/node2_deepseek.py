from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from config import settings
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres el segundo analista (DeepSeek) en un pipeline multi-agente de auditoría de prompts. "
    "Tu función es REVISAR y COMPLEMENTAR el análisis realizado por el primer agente (Gemini).\n\n"
    "Debes:\n"
    "1. Leer el prompt original y el análisis de Gemini\n"
    "2. Indicar si ESTÁS DE ACUERDO o NO con cada hallazgo\n"
    "3. Añadir hallazgos adicionales que Gemini haya pasado por alto\n"
    "4. Ajustar la severidad si consideras que está mal valorada\n"
    "5. Proporcionar TU propia puntuación de riesgo del 0 al 1\n\n"
    "Sé crítico y riguroso. No te limites a repetir lo que dijo Gemini."
)


def _build_prompt(original: str, gemini_output: str | None) -> str:
    context = f"{SYSTEM_PROMPT}\n\n=== PROMPT ORIGINAL ===\n{original}\n"
    if gemini_output:
        context += f"\n=== ANÁLISIS DE GEMINI ===\n{gemini_output}\n"
    else:
        context += "\n=== ANÁLISIS DE GEMINI ===\n(No disponible - el nodo anterior falló)\n"
    context += "\n=== TU ANÁLISIS (REVISIÓN) ===\n"
    return context


async def _call(prompt: str) -> dict[str, Any]:
    key = settings.openrouter_api_key
    if not key:
        return {"success": False, "error": "OPENROUTER_API_KEY no configurada", "content": None}

    url = f"{settings.openrouter_base_url}/chat/completions"
    payload = {
        "model": "deepseek/deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
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
                "model": data.get("model", "deepseek/deepseek-chat"),
            }
    except httpx.TimeoutException:
        return {"success": False, "error": "Timeout contacting OpenRouter", "content": None}
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            pass
        return {"success": False, "error": f"OpenRouter {e.response.status_code}: {body}", "content": None}
    except Exception as e:
        return {"success": False, "error": str(e), "content": None}


async def node2_deepseek(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="deepseek", status=AuditStatus.running)

    gemini_output = None
    for n in state.nodes:
        if n.node_name == "gemini" and n.output:
            gemini_output = n.output

    try:
        result = await _call(_build_prompt(state.prompt.content, gemini_output))
        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["content"]
            node_result.token_usage = result.get("token_usage", {})
            node_result.metadata["model"] = result.get("model", "unknown")
        else:
            node_result.status = AuditStatus.failed
            node_result.error = result.get("error", "Unknown error")
    except Exception as e:
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
