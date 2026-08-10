#!/usr/bin/env python3
"""Compare a review report with a baseline using stable finding fingerprints."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from review_common import finding_fingerprint, load_json, save_json


MATERIAL_FIELDS = ("severity", "confidence", "status", "dimension", "title", "impact", "fix", "cost")
SEVERITY_RANK = {"P0": 3, "P1": 2, "P2": 1}


def index_findings(report: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError(f"{label}.findings must be an array")
    indexed: dict[str, dict[str, Any]] = {}
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"{label}.findings[{index}] must be an object")
        fingerprint = finding_fingerprint(finding)
        if fingerprint in indexed:
            first = indexed[fingerprint].get("id", "unknown")
            raise ValueError(
                f"{label} has duplicate fingerprint {fingerprint} for {first} and {finding.get('id', 'unknown')}"
            )
        indexed[fingerprint] = finding
    return indexed


def changed_fields(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    return [field for field in MATERIAL_FIELDS if before.get(field) != after.get(field)]


def is_regression(before: dict[str, Any], after: dict[str, Any]) -> bool:
    if SEVERITY_RANK.get(str(after.get("severity")), 0) > SEVERITY_RANK.get(str(before.get("severity")), 0):
        return True
    if before.get("status") != "confirmed" and after.get("status") == "confirmed":
        return True
    if before.get("confidence") in {"low", "medium"} and after.get("confidence") == "high":
        return True
    return False


def compact(fingerprint: str, finding: dict[str, Any]) -> dict[str, Any]:
    return {
        "fingerprint": fingerprint,
        "id": finding.get("id"),
        "severity": finding.get("severity"),
        "confidence": finding.get("confidence"),
        "status": finding.get("status"),
        "dimension": finding.get("dimension"),
        "title": finding.get("title"),
    }


def compare_reports(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    before = index_findings(baseline, "baseline")
    after = index_findings(current, "current")

    new = [compact(key, after[key]) for key in sorted(after.keys() - before.keys())]
    resolved = [compact(key, before[key]) for key in sorted(before.keys() - after.keys())]
    changed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    for key in sorted(before.keys() & after.keys()):
        fields = changed_fields(before[key], after[key])
        if fields:
            changed.append(
                {
                    "fingerprint": key,
                    "changed_fields": fields,
                    "regression": is_regression(before[key], after[key]),
                    "baseline": compact(key, before[key]),
                    "current": compact(key, after[key]),
                }
            )
        else:
            unchanged.append(compact(key, after[key]))

    regressions = [item for item in changed if item["regression"]]
    return {
        "schema_version": "review-diff-1.0",
        "summary": {
            "baseline_findings": len(before),
            "current_findings": len(after),
            "new": len(new),
            "resolved": len(resolved),
            "changed": len(changed),
            "regressions": len(regressions),
            "unchanged": len(unchanged),
        },
        "new": new,
        "resolved": resolved,
        "changed": changed,
        "unchanged": unchanged,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path, help="Previously accepted review JSON")
    parser.add_argument("current", type=Path, help="Current review JSON")
    parser.add_argument("--output", type=Path, help="Write the diff JSON to this path")
    parser.add_argument("--fail-on-new", choices=["P0", "P1", "P2"], help="Exit 1 for new findings at or above severity")
    args = parser.parse_args()

    try:
        baseline = load_json(args.baseline)
        current = load_json(args.current)
        if not isinstance(baseline, dict) or not isinstance(current, dict):
            raise ValueError("both reports must be JSON objects")
        result = compare_reports(baseline, current)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.output:
        save_json(args.output, result)
    print(json.dumps({"ok": True, **result["summary"]}, ensure_ascii=False, indent=2))
    if args.fail_on_new:
        threshold = SEVERITY_RANK[args.fail_on_new]
        if any(SEVERITY_RANK.get(str(item.get("severity")), 0) >= threshold for item in result["new"]):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
