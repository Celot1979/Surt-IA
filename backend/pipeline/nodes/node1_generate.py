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


async def node1_generate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node = NodeResult(node_name="generate", status=AuditStatus.running)

    prompt = (
        f"Tarea del usuario: {state.prompt.content}\n\n"
        "Instrucciones:\n"
        "1. Genera una solución completa que resuelva exactamente lo que pide el usuario.\n"
        "2. Después de escribirla, revísala críticamente: busca bugs, edge cases, mejoras de seguridad.\n"
        "3. Produce una versión final revisada y mejorada.\n\n"
        "Responde ÚNICAMENTE con un objeto JSON válido en este formato:\n"
        '{"result": "<solución final aquí>", "review_notes": "<breves notas de revisión>"}'
    )

    try:
        key = settings.openrouter_api_key
        if not key:
            raise ValueError("OPENROUTER_API_KEY no configurada")

        async with httpx.AsyncClient(timeout=70) as client:
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
            node.output = parsed.get("result", raw)[:8000]
        except json.JSONDecodeError:
            node.output = raw[:8000]

        node.status = AuditStatus.completed

    except asyncio.TimeoutError:
        node.status = AuditStatus.failed
        node.error = "DeepSeek timeout after 70s"
    except Exception as e:
        node.status = AuditStatus.failed
        node.error = f"Error en generación: {str(e)[:200]}"

    node.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node)
    return state
