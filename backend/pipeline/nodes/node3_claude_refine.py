from __future__ import annotations

import asyncio
import json
import logging
import re
import time

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


async def node3_claude_refine(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node = NodeResult(node_name="claude_refine", status=AuditStatus.running)

    prev_output = state.nodes[-1].output if state.nodes else ""

    prompt = (
        "Eres un refinador de código experto. Revisa y mejora esta solución:\n\n"
        f"{prev_output}\n\n"
        "Mejora claridad, seguridad, robustez y buenas prácticas.\n"
        "Responde ÚNICAMENTE con JSON:\n"
        '{"refined_solution": "<código mejorado>", "improvements": "<lista de cambios>"}'
    )

    proc = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "claude", "-p",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=prompt.encode()),
            timeout=90,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Claude exit {proc.returncode}: {stderr.decode()[:300]}")

        raw = stdout.decode()

        try:
            data = json.loads(_extract_json(raw))
            node.output = data.get("refined_solution", raw)[:8000]
        except json.JSONDecodeError:
            node.output = raw[:8000]

        node.status = AuditStatus.completed

    except asyncio.TimeoutError:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        node.status = AuditStatus.failed
        node.error = "Claude Code timeout after 90s"
    except FileNotFoundError:
        node.status = AuditStatus.completed
        node.output = prev_output
        logger.warning("claude CLI no encontrado. Usando output previo.")
    except Exception as e:
        node.status = AuditStatus.failed
        node.error = str(e)[:200]

    node.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node)
    return state
