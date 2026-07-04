from __future__ import annotations

import logging
import time

from executor import run_raptor_scan
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)


def _build_summary(state: AuditResult) -> str:
    parts = ["Contexto del análisis de LLMs previo al escaneo:"]
    for n in state.nodes:
        if n.output and n.node_name in ("gemini", "deepseek"):
            excerpt = n.output[:500].replace("\n", " ")
            parts.append(f"[{n.node_name}]: {excerpt}")
    return "\n".join(parts)


async def node3_raptor_scan(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_scan", status=AuditStatus.running)

    target_path = state.prompt.target_path
    context = _build_summary(state)

    if not target_path:
        node_result.status = AuditStatus.completed
        node_result.output = (
            f"Raptor Scan saltado (sin ruta de repositorio).\n\n"
            f"Los análisis previos determinaron:\n{context[:2000]}"
        )
        node_result.duration_ms = (time.monotonic() - start) * 1000
        state.add_node(node_result)
        return state

    logger.info("Ejecutando Raptor scan con contexto: %s...", context[:100])

    try:
        result = run_raptor_scan(target_path, timeout=300)

        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = (
                f"Contexto: {context[:500]}\n\n"
                f"Resultado Raptor Scan:\n{result['stdout'][:8000]}"
            )
            node_result.metadata["returncode"] = result["returncode"]
        elif result.get("error"):
            node_result.status = AuditStatus.failed
            node_result.error = result["error"]
        else:
            node_result.status = AuditStatus.failed
            node_result.error = "Raptor scan returned unknown error"
    except Exception as e:
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
