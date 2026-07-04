from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

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
        node = state.nodes[-1] if state.nodes else None
        state.status = AuditStatus.rejected
        state.error = f"Prompt rechazado (riesgo: {report.risk_score:.2f}): {report.violations[0] if report.violations else 'violación de seguridad'}"
        logger.warning("Audit %s rejected: %s", state.audit_id, state.error)
    return state


def should_continue(state: AuditResult) -> Literal["continue", "reject"]:
    if state.status == AuditStatus.rejected:
        return "reject"
    return "continue"


def should_run_node2(state: AuditResult) -> Literal["node2_deepseek", "reject"]:
    if state.status == AuditStatus.failed or state.status == AuditStatus.rejected:
        return "reject"
    return "node2_deepseek"


def should_run_node3(state: AuditResult) -> Literal["node3_raptor_scan", "reject"]:
    if state.status == AuditStatus.failed or state.status == AuditStatus.rejected:
        return "reject"
    return "node3_raptor_scan"


def should_run_node4(state: AuditResult) -> Literal["node4_raptor_validate", "reject"]:
    if state.status == AuditStatus.failed or state.status == AuditStatus.rejected:
        return "reject"
    return "node4_raptor_validate"


def finalize(state: AuditResult) -> AuditResult:
    if state.status not in (AuditStatus.failed, AuditStatus.rejected):
        last_output = state.nodes[-1].output if state.nodes else ""
        state.complete(summary=last_output[:1000] if last_output else "Auditoría completada sin análisis disponible")
    return state


def build_graph() -> StateGraph:
    workflow = StateGraph(AuditResult)

    workflow.add_node("validate_input", node_validate_input)
    workflow.add_node("node1_gemini", node1_gemini)
    workflow.add_node("node2_deepseek", node2_deepseek)
    workflow.add_node("node3_raptor_scan", node3_raptor_scan)
    workflow.add_node("node4_raptor_validate", node4_raptor_validate)
    workflow.add_node("finalize", finalize)

    workflow.set_entry_point("validate_input")

    workflow.add_conditional_edges(
        "validate_input",
        should_continue,
        {"continue": "node1_gemini", "reject": "finalize"},
    )

    workflow.add_conditional_edges(
        "node1_gemini",
        should_run_node2,
        {"node2_deepseek": "node2_deepseek", "reject": "finalize"},
    )

    workflow.add_conditional_edges(
        "node2_deepseek",
        should_run_node3,
        {"node3_raptor_scan": "node3_raptor_scan", "reject": "finalize"},
    )

    workflow.add_conditional_edges(
        "node3_raptor_scan",
        should_run_node4,
        {"node4_raptor_validate": "node4_raptor_validate", "reject": "finalize"},
    )

    workflow.add_edge("node4_raptor_validate", "finalize")
    workflow.add_edge("finalize", END)

    return workflow


graph = build_graph()
