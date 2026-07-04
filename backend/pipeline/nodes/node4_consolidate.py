from __future__ import annotations

import asyncio
import json
import logging
import re
import time

import httpx

from config import settings
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> str:
    text = re.sub(r'```(?:json)?\s*', '', text)
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start:i+1]
    return text.strip()


async def node4_consolidate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node = NodeResult(node_name="consolidate", status=AuditStatus.running)

    partes = []
    for n in state.nodes:
        if n.output:
            partes.append(f"=== {n.node_name.upper()} ===\n{n.output}")
    context = "\n\n".join(partes) if partes else "No hay trabajo previo."

    prompt = (
        "Eres el consolidador final de un pipeline multi-agente.\n"
        "Toma el trabajo de los agentes anteriores y produce la VERSIÓN FINAL ÚNICA:\n\n"
        f"{context}\n\n"
        "Debes:\n"
        "1. Tomar lo mejor de cada agente\n"
        "2. Eliminar duplicados\n"
        "3. Asegurar que cumple exactamente lo que pidió el usuario\n"
        "4. Dar formato limpio y profesional\n\n"
        "Responde ÚNICAMENTE con JSON:\n"
        '{"final_result": "<versión final>", "summary": "<resumen breve de lo que se hizo>"}'
    )

    try:
        key = settings.openrouter_api_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY no configurada")

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://surt-ia.local",
                    "X-Title": "SurtIA",
                },
                json={
                    "model": "deepseek/deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 3000,
                },
            )

        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter {resp.status_code}: {resp.text[:300]}")

        raw = resp.json()["choices"][0]["message"]["content"]

        try:
            parsed = json.loads(_extract_json(raw))
            node.output = parsed.get("final_result", raw)[:8000]
            summary = parsed.get("summary", "")
        except json.JSONDecodeError:
            node.output = raw[:8000]
            summary = ""

        node.status = AuditStatus.completed
        state.complete(summary=summary or node.output[:500])

    except asyncio.TimeoutError:
        node.status = AuditStatus.failed
        node.error = "Consolidación timeout after 30s"
    except Exception as e:
        node.status = AuditStatus.completed
        node.output = context
        node.error = str(e)[:200]
        state.complete(summary=context[:500])

    node.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node)
    return state
