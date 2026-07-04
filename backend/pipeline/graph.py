from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from pipeline.models import AuditResult, AuditStatus
from pipeline.nodes.node1_gemini import node1_gemini
from pipeline.nodes.node2_deepseek import node2_deepseek
from pipeline.nodes.node4_raptor_validate import node4_raptor_validate
from pipeline.security import validate_prompt

logger = logging.getLogger(__name__)


def node_validate_input(state: AuditResult) -> AuditResult:
    report = validate_prompt(state.prompt)
    if not report.is_valid:
        state.status = AuditStatus.rejected
        state.error = (
            f"Prompt rechazado (riesgo: {report.risk_score:.2f})"
        )
    return state


def gate(state: AuditResult) -> Literal["ok", "abort"]:
    if not state.nodes:
        return "ok"
    last = state.nodes[-1]
    if last.status in (AuditStatus.failed, AuditStatus.rejected):
        return "abort"
    return "ok"


workflow = StateGraph(AuditResult)

workflow.add_node("validate_input", node_validate_input)
workflow.add_node("node1_gemini", node1_gemini)
workflow.add_node("node2_deepseek", node2_deepseek)
workflow.add_node("node4_raptor_validate", node4_raptor_validate)

workflow.add_edge(START, "validate_input")
workflow.add_conditional_edges("validate_input", gate, {"ok": "node1_gemini", "abort": END})
workflow.add_conditional_edges("node1_gemini", gate, {"ok": "node2_deepseek", "abort": END})
workflow.add_conditional_edges("node2_deepseek", gate, {"ok": "node4_raptor_validate", "abort": END})
workflow.add_edge("node4_raptor_validate", END)

graph = workflow.compile()
