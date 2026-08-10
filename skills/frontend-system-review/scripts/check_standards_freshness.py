#!/usr/bin/env python3
"""Validate the versioned standards baseline and fail when its review is stale."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from review_common import SKILL_ROOT, load_json, tool_version


DEFAULT_BASELINE = SKILL_ROOT / "references" / "standards-baseline.json"


def parse_date(value: Any, field: str) -> dt.date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date") from exc


def require_https(value: Any, field: str) -> None:
    if not isinstance(value, str) or urlsplit(value).scheme != "https":
        raise ValueError(f"{field} must be an https URL")


def validate(data: dict[str, Any], today: dt.date) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        if data.get("schema_version") != "frontend-review-standards-1.0":
            errors.append("unsupported schema_version")
        version = tool_version()
        if data.get("skill_version") != version:
            errors.append(f"skill_version must match VERSION ({version})")
        reviewed = parse_date(data.get("reviewed_on"), "reviewed_on")
        due = parse_date(data.get("review_due"), "review_due")
        if due < reviewed:
            errors.append("review_due cannot be earlier than reviewed_on")
        maximum_age = data.get("policy", {}).get("maximum_review_age_days")
        if not isinstance(maximum_age, int) or isinstance(maximum_age, bool) or maximum_age < 1:
            errors.append("policy.maximum_review_age_days must be a positive integer")
        elif (due - reviewed).days > maximum_age:
            errors.append("review_due exceeds policy.maximum_review_age_days")
        if today > due:
            errors.append(f"standards baseline expired on {due.isoformat()}")
        elif (due - today).days <= 14:
            warnings.append(f"standards baseline review is due in {(due - today).days} days")

        standards = data.get("standards")
        if not isinstance(standards, dict):
            errors.append("standards must be an object")
        else:
            wcag = standards.get("wcag", {})
            if wcag.get("version") != "2.2" or wcag.get("conformance_target") != "AA":
                errors.append("WCAG baseline must explicitly identify WCAG 2.2 AA")
            require_https(wcag.get("source"), "standards.wcag.source")

            vitals = standards.get("core_web_vitals", {})
            thresholds = vitals.get("good_thresholds", {})
            expected = {"lcp_ms": 2500, "inp_ms": 200, "cls": 0.1}
            if thresholds != expected or vitals.get("assessment_percentile") != 75:
                errors.append("Core Web Vitals snapshot does not match the reviewed thresholds")
            require_https(vitals.get("source"), "standards.core_web_vitals.source")

            sarif = standards.get("sarif", {})
            if sarif.get("version") != "2.1.0":
                errors.append("SARIF baseline must identify version 2.1.0")
            require_https(sarif.get("source"), "standards.sarif.source")

        compatibility = data.get("runtime_compatibility")
        if not isinstance(compatibility, dict):
            errors.append("runtime_compatibility must be an object")
        else:
            if not re.fullmatch(r">=\d+(?:\.\d+)?", str(compatibility.get("python", ""))):
                errors.append("runtime_compatibility.python must be an explicit minimum")
            if not re.fullmatch(r">=\d+(?:\.\d+)?", str(compatibility.get("node", ""))):
                errors.append("runtime_compatibility.node must be an explicit minimum")
            systems = compatibility.get("operating_systems")
            if systems != ["Linux", "macOS", "Windows"]:
                errors.append("runtime_compatibility.operating_systems must cover Linux, macOS and Windows")
    except ValueError as exc:
        errors.append(str(exc))

    return {
        "valid": not errors,
        "checked_on": today.isoformat(),
        "reviewed_on": data.get("reviewed_on"),
        "review_due": data.get("review_due"),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help="Override date for deterministic tests")
    args = parser.parse_args()
    try:
        data = load_json(args.baseline)
        if not isinstance(data, dict):
            raise ValueError("standards baseline must be a JSON object")
        result = validate(data, args.today)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result = {"valid": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
