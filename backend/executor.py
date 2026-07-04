from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

RAPTOR_DIR = settings.raptor_dir
RAPTOR_BIN = settings.raptor_bin


def _build_env() -> dict[str, str]:
    env = os.environ.copy()
    env["RAPTOR_DIR"] = str(RAPTOR_DIR)
    env["_RAPTOR_TRUSTED"] = "1"
    env["PYTHONPATH"] = f"{RAPTOR_DIR}:{env.get('PYTHONPATH', '')}"
    if "ANTHROPIC_API_KEY" in env:
        env["ANTHROPIC_API_KEY"] = env["ANTHROPIC_API_KEY"]
    return env


def run_raptor_scan(
    target_path: str,
    timeout: int = 300,
) -> dict[str, Any]:
    start = time.monotonic()
    result: dict[str, Any] = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "duration_ms": 0.0,
        "error": None,
    }

    cmd = [sys.executable, str(RAPTOR_DIR / "raptor.py"), "scan", "--repo", target_path]

    logger.info("Ejecutando Raptor scan: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
            cwd=str(RAPTOR_DIR),
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["returncode"] = proc.returncode
        result["success"] = proc.returncode == 0

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip()
            result["error"] = f"Raptor scan failed (rc={proc.returncode}): {error_msg[:500]}"
            logger.error("Raptor scan failed: %s", result["error"])

    except subprocess.TimeoutExpired:
        result["error"] = f"Raptor scan timed out after {timeout}s"
        logger.error(result["error"])
    except FileNotFoundError:
        result["error"] = f"Raptor no encontrado en {RAPTOR_DIR / 'raptor.py'}"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = f"Error inesperado ejecutando Raptor: {e}"
        logger.exception(result["error"])

    result["duration_ms"] = (time.monotonic() - start) * 1000
    return result


def run_raptor_agentic(
    target_path: str,
    timeout: int = 600,
) -> dict[str, Any]:
    start = time.monotonic()
    result: dict[str, Any] = {
        "success": False,
        "stdout": "",
        "stderr": "",
        "returncode": -1,
        "duration_ms": 0.0,
        "error": None,
    }

    cmd = [
        sys.executable,
        str(RAPTOR_DIR / "raptor.py"),
        "agentic",
        "--repo",
        target_path,
        "--no-codeql",
    ]

    logger.info("Ejecutando Raptor agentic: %s", " ".join(cmd))

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_build_env(),
            cwd=str(RAPTOR_DIR),
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["returncode"] = proc.returncode
        result["success"] = proc.returncode == 0

        if proc.returncode != 0:
            error_msg = proc.stderr.strip() or proc.stdout.strip()
            result["error"] = f"Raptor agentic failed (rc={proc.returncode}): {error_msg[:500]}"
            logger.error("Raptor agentic failed: %s", result["error"])

    except subprocess.TimeoutExpired:
        result["error"] = f"Raptor agentic timed out after {timeout}s"
        logger.error(result["error"])
    except FileNotFoundError:
        result["error"] = f"Raptor no encontrado en {RAPTOR_DIR / 'raptor.py'}"
        logger.error(result["error"])
    except Exception as e:
        result["error"] = f"Error inesperado ejecutando Raptor agentic: {e}"
        logger.exception(result["error"])

    result["duration_ms"] = (time.monotonic() - start) * 1000
    return result


def healthcheck() -> dict[str, Any]:
    status = {
        "raptor_installed": RAPTOR_DIR.exists(),
        "raptor_bin": RAPTOR_BIN.exists(),
        "raptor_main_py": (RAPTOR_DIR / "raptor.py").exists(),
        "raptor_dir": str(RAPTOR_DIR),
    }

    if status["raptor_installed"]:
        try:
            proc = subprocess.run(
                [sys.executable, str(RAPTOR_DIR / "raptor.py"), "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                env=_build_env(),
                cwd=str(RAPTOR_DIR),
            )
            status["raptor_version"] = proc.stdout.strip() or "unknown"
        except Exception as e:
            status["raptor_version"] = f"error: {e}"

    return status
