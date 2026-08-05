#!/usr/bin/env python3
"""Shared constants and JSON helpers for frontend-system-review tooling."""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


SCHEMA_VERSION = "1.0"

DIMENSIONS: dict[str, tuple[str, int]] = {
    "business_architecture_fit": ("业务与架构匹配", 8),
    "stack_dependencies_build": ("技术栈、依赖与构建", 8),
    "module_boundaries": ("模块边界与可维护性", 10),
    "types_api_data": ("类型、API 与数据正确性", 10),
    "state_routing_rendering": ("状态、路由与渲染", 8),
    "performance_seo": ("性能与 SEO", 10),
    "ui_responsive_design": ("UI、响应式与设计系统", 8),
    "accessibility": ("可访问性", 8),
    "testing": ("测试体系", 8),
    "ci_release_recovery": ("CI/CD 与发布恢复", 10),
    "security_privacy_supply_chain": ("安全、隐私与供应链", 8),
    "observability_operations": ("可观测性与运维", 4),
}

SEVERITIES = {"P0", "P1", "P2"}
CONFIDENCES = {"high", "medium", "low"}
FINDING_STATUSES = {"confirmed", "likely"}
MODES = {"repository", "change", "runtime", "proposal"}
DEPTHS = {"quick", "standard", "deep"}
CONCLUSIONS = {
    "block",
    "ready_after_fixes",
    "ready_with_followups",
    "acceptable",
    "unable_to_determine",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def finding_fingerprint(finding: dict[str, Any]) -> str:
    """Return a stable logical identity for baseline matching and SARIF."""
    explicit = finding.get("fingerprint")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    evidence = finding.get("evidence") if isinstance(finding.get("evidence"), list) else []
    anchors: list[str] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "unknown")
        if kind == "source":
            file_value = str(item.get("file") or "").replace("\\", "/").casefold()
            quote = normalize_whitespace(str(item.get("quote") or "")).casefold()
            anchors.append(f"source:{file_value}:{quote}")
        elif kind == "runtime":
            raw_url = str(item.get("url") or "")
            try:
                parsed = urlsplit(raw_url)
                stable_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            except ValueError:
                stable_url = raw_url.split("?", 1)[0]
            viewport = normalize_whitespace(str(item.get("viewport") or "")).casefold()
            anchors.append(f"runtime:{stable_url.casefold()}:{viewport}")
        elif kind == "tool":
            artifact = Path(str(item.get("artifact") or "")).name.casefold()
            anchors.append(f"tool:{artifact}")
    if not anchors:
        anchors.append("unanchored")

    canonical = "\n".join(
        [
            "fsr-finding-v1",
            normalize_whitespace(str(finding.get("dimension") or "")).casefold(),
            normalize_whitespace(str(finding.get("title") or "")).casefold(),
            *sorted(set(anchors)),
        ]
    )
    return f"fsr1:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:24]}"


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def grade_for(total: float) -> str:
    if total >= 85:
        return "A"
    if total >= 70:
        return "B"
    if total >= 55:
        return "C"
    return "D"
