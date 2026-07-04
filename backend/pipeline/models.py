from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AuditSeverity(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    info = "info"


class AuditStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class PromptInput(BaseModel):
    prompt_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    content: str = Field(..., min_length=1, max_length=100_000)
    target_path: str | None = Field(None, description="Path al repositorio a auditar")
    use_raptor: bool = Field(False, description="Activar escaneo Raptor")
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def sanitize_content(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("El prompt no puede estar vacío")
        return stripped


class NodeResult(BaseModel):
    node_name: str
    status: AuditStatus
    output: str | None = None
    error: str | None = None
    severity: AuditSeverity | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    token_usage: dict[str, int] = Field(default_factory=dict)
    duration_ms: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditResult(BaseModel):
    audit_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    prompt: PromptInput
    status: AuditStatus = AuditStatus.pending
    nodes: list[NodeResult] = Field(default_factory=list)
    summary: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    error: str | None = None

    def add_node(self, node_result: NodeResult) -> None:
        self.nodes.append(node_result)

    def complete(self, summary: str | None = None) -> None:
        self.status = AuditStatus.completed
        self.completed_at = datetime.now(timezone.utc)
        self.summary = summary

    def fail(self, error: str) -> None:
        self.status = AuditStatus.failed
        self.completed_at = datetime.now(timezone.utc)
        self.error = error


class ValidationReport(BaseModel):
    is_valid: bool
    risk_score: float = Field(..., ge=0.0, le=1.0)
    violations: list[str] = Field(default_factory=list)
    sanitized_content: str | None = None
