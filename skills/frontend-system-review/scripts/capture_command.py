#!/usr/bin/env python3
"""Run an explicit command and save complete redacted stdout/stderr evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from review_common import save_json


REDACTIONS = [
    re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+"),
    re.compile(r"(?i)((?:api[_-]?key|access[_-]?token|token|secret|password)\s*[=:]\s*)[^\s,;]+"),
]


def redact(value: str) -> tuple[str, int]:
    count = 0
    output = value
    for pattern in REDACTIONS:
        output, replacements = pattern.subn(r"\1[redacted]", output)
        count += replacements
    return output, count


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_label(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", value):
        raise ValueError("--label must contain 1-80 letters, digits, dots, underscores, or hyphens")
    return value


def write_log(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True, help="Command working directory")
    parser.add_argument("--output", type=Path, required=True, help="Evidence output directory")
    parser.add_argument("--label", required=True, help="Stable filename label")
    parser.add_argument("--timeout", type=float, default=600, help="Timeout in seconds (default: 600)")
    parser.add_argument("--fail-on-command-error", action="store_true", help="Exit 1 when the captured command is non-zero")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command after --")
    args = parser.parse_args()

    try:
        label = safe_label(args.label)
        cwd = args.cwd.resolve()
        if not cwd.is_dir():
            raise ValueError(f"working directory does not exist: {cwd}")
        if not args.command:
            raise ValueError("provide a command after --")
        command = args.command[1:] if args.command[0] == "--" else args.command
        if not command:
            raise ValueError("provide a command after --")
        if isinstance(args.timeout, bool) or not isinstance(args.timeout, (int, float)) or not 0 < args.timeout <= 86400:
            raise ValueError("--timeout must be greater than 0 and at most 86400 seconds")
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    started_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, check=False, timeout=args.timeout)
        stdout_bytes = result.stdout
        stderr_bytes = result.stderr
        exit_code: int | None = result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_bytes = exc.stdout or b""
        stderr_bytes = exc.stderr or b""
        exit_code = None
        timed_out = True
    except OSError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    stdout_text, stdout_redactions = redact(stdout_bytes.decode("utf-8", errors="replace"))
    stderr_text, stderr_redactions = redact(stderr_bytes.decode("utf-8", errors="replace"))
    redacted_command = []
    command_redactions = 0
    for token in command:
        redacted, count = redact(str(token))
        redacted_command.append(redacted)
        command_redactions += count

    stdout_path = output / f"{label}.stdout.log"
    stderr_path = output / f"{label}.stderr.log"
    metadata_path = output / f"{label}.json"
    write_log(stdout_path, stdout_text)
    write_log(stderr_path, stderr_text)
    metadata: dict[str, Any] = {
        "schema_version": "command-evidence-1.0",
        "label": label,
        "command": redacted_command,
        "cwd": str(cwd),
        "started_at": started_at,
        "duration_ms": round((time.monotonic() - started) * 1000),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "capture": {
            "complete": not timed_out,
            "stdout_original_bytes": len(stdout_bytes),
            "stderr_original_bytes": len(stderr_bytes),
            "redactions_applied": stdout_redactions + stderr_redactions + command_redactions,
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "os_name": os.name,
        },
        "artifacts": {
            "stdout": {"path": stdout_path.name, "bytes": stdout_path.stat().st_size, "sha256": sha256(stdout_path)},
            "stderr": {"path": stderr_path.name, "bytes": stderr_path.stat().st_size, "sha256": sha256(stderr_path)},
        },
    }
    save_json(metadata_path, metadata)
    payload = {"ok": not timed_out and exit_code == 0, "metadata": str(metadata_path), "exit_code": exit_code, "timed_out": timed_out}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if timed_out:
        return 1
    if args.fail_on_command_error and exit_code != 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
