from __future__ import annotations

import logging
from typing import Literal

from langgraph.graph import END, START, StateGraph

from pipeline.models import AuditResult, AuditStatus
from pipeline.nodes.node1_generate import node1_generate
from pipeline.nodes.node3_claude_refine import node3_claude_refine
from pipeline.nodes.node4_consolidate import node4_consolidate

logger = logging.getLogger(__name__)


def node_validate_input(state: AuditResult) -> AuditResult:
    content = state.prompt.content.strip()
    if not content:
        state.status = AuditStatus.rejected
        state.error = "El prompt está vacío"
    elif len(content) < 3:
        state.status = AuditStatus.rejected
        state.error = "Prompt demasiado corto (mínimo 3 caracteres)"
    return state


def gate(state: AuditResult) -> Literal["ok", "abort"]:
    if state.status in (AuditStatus.rejected, AuditStatus.failed):
        return "abort"
    if state.nodes:
        last = state.nodes[-1]
        if last.status in (AuditStatus.failed, AuditStatus.rejected):
            return "abort"
    return "ok"


workflow = StateGraph(AuditResult)

workflow.add_node("validate_input", node_validate_input)
workflow.add_node("node1_generate", node1_generate)
workflow.add_node("node3_claude_refine", node3_claude_refine)
workflow.add_node("node4_consolidate", node4_consolidate)

workflow.add_edge(START, "validate_input")
workflow.add_conditional_edges("validate_input", gate, {"ok": "node1_generate", "abort": END})
workflow.add_conditional_edges("node1_generate", gate, {"ok": "node3_claude_refine", "abort": END})
workflow.add_conditional_edges("node3_claude_refine", gate, {"ok": "node4_consolidate", "abort": END})
workflow.add_edge("node4_consolidate", END)

graph = workflow.compile()
