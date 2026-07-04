from __future__ import annotations

import logging
import re
from typing import Final

from .models import PromptInput, ValidationReport

logger = logging.getLogger(__name__)

SUSPICIOUS_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"ignora\s+(las\s+)?instrucciones", re.IGNORECASE),
    re.compile(r"olvida\s+(todo\s+)?lo\s+anterior", re.IGNORECASE),
    re.compile(r"omite\s+(las\s+)?restricciones", re.IGNORECASE),
    re.compile(r'system\s*:\s*".*?"', re.IGNORECASE | re.DOTALL),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"prompt\s+injection", re.IGNORECASE),
    re.compile(r"role\s*:\s*system", re.IGNORECASE),
]

INJECTION_PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", re.IGNORECASE),
    re.compile(r"(?:SELECT|INSERT|UPDATE|DELETE|DROP|UNION).*(?:FROM|INTO|TABLE)", re.IGNORECASE),
    re.compile(r"(?:javascript|eval|exec|sp_executesql|xp_cmdshell)\s*\(", re.IGNORECASE),
    re.compile(r"(?:rm\s+-rf|format\s+|:!bash|:!sh)", re.IGNORECASE),
    re.compile(r"(?:https?:\/\/)?(?:localhost|127\.0\.0\.1|0\.0\.0\.0)(?::\d+)?\/?(?:api|admin|internal)", re.IGNORECASE),
]


def validate_prompt(prompt: PromptInput) -> ValidationReport:
    violations: list[str] = []
    risk_score = 0.0
    sanitized = prompt.content

    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(prompt.content):
            match = pattern.search(prompt.content)
            violations.append(f"Patrón sospechoso detectado: {match.group()[:80]!r}")
            risk_score += 0.25

    for pattern in INJECTION_PATTERNS:
        if pattern.search(prompt.content):
            match = pattern.search(prompt.content)
            violations.append(f"Patrón de inyección detectado: {match.group()[:80]!r}")
            risk_score += 0.35

    if len(prompt.content) > 10_000:
        violations.append(f"Prompt extenso ({len(prompt.content)} caracteres)")
        risk_score += 0.1

    if prompt.content != prompt.content.strip():
        sanitized = prompt.content.strip()
        violations.append("Se eliminaron espacios en blanco al inicio/final")

    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", sanitized)

    risk_score = min(risk_score, 1.0)

    is_valid = risk_score < 0.7

    if not is_valid:
        logger.warning(
            "Prompt rejected: risk_score=%.2f, violations=%s",
            risk_score,
            violations,
        )

    return ValidationReport(
        is_valid=is_valid,
        risk_score=risk_score,
        violations=violations,
        sanitized_content=sanitized if violations else None,
    )
