#!/usr/bin/env python3
"""Calculate weighted score and evidence coverage for a review JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from review_common import DIMENSIONS, grade_for, load_json, save_json


def calculate(scoring: dict[str, Any], require_all: bool) -> dict[str, Any]:
    dimensions = scoring.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("scoring.dimensions must be an object")

    unknown = sorted(set(dimensions) - set(DIMENSIONS))
    if unknown:
        raise ValueError(f"unknown scoring dimensions: {', '.join(unknown)}")
    if require_all:
        missing = sorted(set(DIMENSIONS) - set(dimensions))
        if missing:
            raise ValueError(f"missing scoring dimensions: {', '.join(missing)}")

    applicable_weight = 0
    earned_weight = 0.0
    evidence_weight = 0
    details: dict[str, Any] = {}

    for key, entry in dimensions.items():
        if not isinstance(entry, dict):
            raise ValueError(f"scoring.dimensions.{key} must be an object")
        label, weight = DIMENSIONS[key]
        score = entry.get("score")
        evidence_sufficient = entry.get("evidence_sufficient")
        note = entry.get("note")
        if not isinstance(note, str):
            raise ValueError(f"scoring.dimensions.{key}.note must be a string")
        if score is None:
            details[key] = {"label": label, "weight": weight, "applicable": False, "weighted_score": None}
            continue
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 5:
            raise ValueError(f"scoring.dimensions.{key}.score must be null or a number from 0 to 5")
        if not isinstance(evidence_sufficient, bool):
            raise ValueError(f"scoring.dimensions.{key}.evidence_sufficient must be boolean")
        weighted_score = weight * float(score) / 5
        applicable_weight += weight
        earned_weight += weighted_score
        if evidence_sufficient:
            evidence_weight += weight
        details[key] = {
            "label": label,
            "weight": weight,
            "applicable": True,
            "score": float(score),
            "evidence_sufficient": evidence_sufficient,
            "weighted_score": round(weighted_score, 2),
        }

    if applicable_weight == 0:
        raise ValueError("at least one scoring dimension must be applicable")
    total = earned_weight / applicable_weight * 100
    coverage = evidence_weight / applicable_weight * 100
    return {
        "total": round(total, 1),
        "grade": grade_for(total),
        "evidence_coverage": round(coverage, 1),
        "status": "final" if coverage >= 70 else "provisional",
        "applicable_weight": applicable_weight,
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to review JSON")
    parser.add_argument("--write", action="store_true", help="Write calculated results back to the report")
    parser.add_argument("--require-all", action="store_true", help="Require all known dimensions to be present")
    args = parser.parse_args()

    try:
        report = load_json(args.report)
        if not isinstance(report, dict) or not isinstance(report.get("scoring"), dict):
            raise ValueError("report must contain a scoring object")
        result = calculate(report["scoring"], args.require_all)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    if args.write:
        report["scoring"]["result"] = result
        save_json(args.report, report)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
