from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from pipeline.models import AuditResult, AuditStatus
from pipeline.nodes.node1_gemini import node1_gemini
from pipeline.nodes.node2_deepseek import node2_deepseek
from pipeline.nodes.node3_raptor_scan import node3_raptor_scan
from pipeline.nodes.node4_raptor_validate import node4_raptor_validate
from pipeline.security import validate_prompt

logger = logging.getLogger(__name__)


def node_validate_input(state: AuditResult) -> AuditResult:
    report = validate_prompt(state.prompt)
    if not report.is_valid:
        state.status = AuditStatus.rejected
        state.error = (
            f"Prompt rechazado (riesgo: {report.risk_score:.2f}): "
            f"{report.violations[0] if report.violations else 'violación de seguridad'}"
        )
    return state


def _last_failed(state: AuditResult) -> bool:
    if not state.nodes:
        return False
    return state.nodes[-1].status in (AuditStatus.failed, AuditStatus.rejected)


def _gate(state: AuditResult) -> Literal["continue", "abort"]:
    if _last_failed(state) or state.status == AuditStatus.rejected:
        return "abort"
    return "continue"


NEXT_GEMINI = {"continue": "node1_gemini", "abort": "finalize"}
NEXT_DEEPSEEK = {"continue": "node2_deepseek", "abort": "finalize"}
NEXT_RAPTOR_SCAN = {"continue": "node3_raptor_scan", "abort": "finalize"}
NEXT_RAPTOR_VALIDATE = {"continue": "node4_raptor_validate", "abort": "finalize"}


def node_finalize(state: AuditResult) -> AuditResult:
    if state.status not in (AuditStatus.failed, AuditStatus.rejected):
        outputs = [
            f"[{n.node_name}] {n.output[:200].replace(chr(10), ' ')}"
            for n in state.nodes
            if n.output
        ]
        if not state.summary:
            state.complete(summary="\n".join(outputs) if outputs else "Auditoría completada")
    return state


workflow = StateGraph(AuditResult)

workflow.add_node("validate_input", node_validate_input)
workflow.add_node("node1_gemini", node1_gemini)
workflow.add_node("node2_deepseek", node2_deepseek)
workflow.add_node("node3_raptor_scan", node3_raptor_scan)
workflow.add_node("node4_raptor_validate", node4_raptor_validate)
workflow.add_node("finalize", node_finalize)

workflow.add_edge(START, "validate_input")
workflow.add_conditional_edges("validate_input", _gate, NEXT_GEMINI)
workflow.add_conditional_edges("node1_gemini", _gate, NEXT_DEEPSEEK)
workflow.add_conditional_edges("node2_deepseek", _gate, NEXT_RAPTOR_SCAN)
workflow.add_conditional_edges("node3_raptor_scan", _gate, NEXT_RAPTOR_VALIDATE)
workflow.add_edge("node4_raptor_validate", "finalize")
workflow.add_edge("finalize", END)

graph = workflow.compile()
