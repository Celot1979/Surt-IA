from __future__ import annotations

import logging
import time
from typing import Any

from executor import run_raptor_scan
from pipeline.models import AuditResult, AuditStatus, NodeResult

logger = logging.getLogger(__name__)


def _parse_scan_output(stdout: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not stdout:
        return findings

    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("OUTPUT_DIR"):
            continue
        if "finding" in line.lower() or "vulnerability" in line.lower() or "issue" in line.lower():
            findings.append({"raw": line[:500], "source": "raptor_scan"})

    return findings


async def node3_raptor_scan(state: AuditResult) -> AuditResult:
    start = time.monotonic()
    node_result = NodeResult(node_name="raptor_scan", status=AuditStatus.running)

    target_path = state.prompt.target_path
    if not target_path:
        node_result.status = AuditStatus.failed
        node_result.error = "target_path requerido para Raptor scan"
        node_result.duration_ms = (time.monotonic() - start) * 1000
        state.add_node(node_result)
        return state

    try:
        result = run_raptor_scan(target_path, timeout=300)

        if result["success"]:
            node_result.status = AuditStatus.completed
            node_result.output = result["stdout"][:10_000] if result["stdout"] else ""
            node_result.findings = _parse_scan_output(result["stdout"])
            node_result.metadata["returncode"] = result["returncode"]
        else:
            node_result.status = AuditStatus.failed
            node_result.error = result.get("error", "Raptor scan returned unknown error")

    except Exception as e:
        logger.exception("Node 3 (Raptor Scan) critical failure")
        node_result.status = AuditStatus.failed
        node_result.error = str(e)

    node_result.duration_ms = (time.monotonic() - start) * 1000
    state.add_node(node_result)
    return state
