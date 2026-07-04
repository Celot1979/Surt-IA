from __future__ import annotations

import logging
import time
from typing import Any

from executor import run_raptor_agentic
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)


def _parse_agentic_output(stdout: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not stdout:
        return findings

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(kw in line.lower() for kw in ["finding", "vulnerability", "exploit", "cve", "severity"]):
            findings.append({"raw": line[:500], "source": "raptor_agentic"})

    return findings


async def node4_raptor_validate(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_validate", status=AuditStatus.running)

    target_path = state.prompt.target_path
    if not target_path:
        node_result.status = AuditStatus.failed
        node_result.error = "target_path requerido para Raptor validate"
        node_result.duration_ms = (time.monotonic() - start) * 1000
        state.add_node(node_result)
        return state

    try:
        result = run_raptor_agentic(target_path, timeout=600)

        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["stdout"][:10_000] if result["stdout"] else ""
            node_result.findings = _parse_agentic_output(result["stdout"])
            node_result.metadata["returncode"] = result["returncode"]
        else:
            node_result.status = AuditStatus.failed
            node_result.error = result.get("error", "Raptor validate returned unknown error")

    except Exception as e:
        logger.exception("Node 4 (Raptor Validate) critical failure")
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
