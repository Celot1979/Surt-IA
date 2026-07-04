from __future__ import annotations

import logging
import time

from executor import run_raptor_agentic
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)


async def node4_raptor_validate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_validate", status=AuditStatus.running)

    target_path = state.prompt.target_path

    if not target_path:
        node_result.status = AuditStatus.completed
        node_result.output = "No se proporcionó ruta de repositorio para validar. Raptor saltado."
        node_result.duration_ms = (time.monotonic() - start) * 1000
        state.add_node(node_result)
        return state

    try:
        result = run_raptor_agentic(target_path, timeout=600)

        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["stdout"][:10_000] if result["stdout"] else "Raptor validación completada."
            node_result.metadata["returncode"] = result["returncode"]
        elif result.get("error"):
            node_result.status = AuditStatus.failed
            node_result.error = result["error"]
        else:
            node_result.status = AuditStatus.failed
            node_result.error = "Raptor validate returned unknown error"

    except Exception as e:
        logger.exception("Node 4 (Raptor Validate) critical failure")
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
