#!/usr/bin/env python3
"""Export source-located review findings as GitHub-compatible SARIF 2.1.0."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

from review_common import DIMENSIONS, finding_fingerprint, load_json, save_json


LEVELS = {"P0": "error", "P1": "warning", "P2": "note"}


def source_evidence(finding: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = finding.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [item for item in evidence if isinstance(item, dict) and item.get("kind") == "source" and item.get("file")]


def location(item: dict[str, Any], identifier: int | None = None) -> dict[str, Any]:
    file_value = str(item["file"]).replace("\\", "/")
    output: dict[str, Any] = {
        "physicalLocation": {
            "artifactLocation": {"uri": quote(file_value, safe="/._-"), "uriBaseId": "%SRCROOT%"},
            "region": {
                "startLine": int(item.get("line") or 1),
                "endLine": int(item.get("end_line") or item.get("line") or 1),
            },
        },
        "message": {"text": str(item.get("summary") or "Source evidence")[:1024]},
    }
    if identifier is not None:
        output["id"] = identifier
    return output


def to_sarif(report: dict[str, Any], include_likely: bool, category: str) -> tuple[dict[str, Any], int]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise ValueError("report.findings must be an array")
    eligible: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    skipped = 0
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("every finding must be an object")
        if finding.get("status") != "confirmed" and not include_likely:
            skipped += 1
            continue
        sources = source_evidence(finding)
        if not sources:
            skipped += 1
            continue
        eligible.append((finding, sources))

    dimensions = sorted({str(finding.get("dimension") or "other") for finding, _ in eligible})
    rule_indexes = {dimension: index for index, dimension in enumerate(dimensions)}
    rules = []
    for dimension in dimensions:
        label = DIMENSIONS.get(dimension, (dimension.replace("_", " ").title(), 0))[0]
        rules.append(
            {
                "id": f"FSR.{dimension}",
                "name": dimension[:255],
                "shortDescription": {"text": label[:1024]},
                "fullDescription": {"text": f"Frontend System Review finding in {label}."[:1024]},
                "defaultConfiguration": {"level": "warning"},
                "help": {
                    "text": "Confirm the evidence, apply the smallest safe fix, and run the finding verification steps.",
                    "markdown": "Confirm the cited evidence, apply the smallest safe fix, and run the finding's verification steps.",
                },
                "properties": {"tags": ["frontend-system-review", dimension]},
            }
        )

    results = []
    for finding, sources in eligible:
        dimension = str(finding.get("dimension") or "other")
        fingerprint = finding_fingerprint(finding)
        verification = finding.get("verification") if isinstance(finding.get("verification"), list) else []
        message = f"{finding.get('title')}. Impact: {finding.get('impact')} Fix: {finding.get('fix')}"
        if verification:
            message += f" Verify: {'; '.join(str(item) for item in verification)}"
        result: dict[str, Any] = {
            "ruleId": f"FSR.{dimension}",
            "ruleIndex": rule_indexes[dimension],
            "level": LEVELS.get(str(finding.get("severity")), "warning"),
            "message": {"text": message[:4096]},
            "locations": [location(sources[0])],
            "partialFingerprints": {"primaryLocationLineHash": f"{fingerprint.replace(':', '')}:1"},
            "properties": {
                "findingId": finding.get("id"),
                "fingerprint": fingerprint,
                "severity": finding.get("severity"),
                "confidence": finding.get("confidence"),
                "status": finding.get("status"),
                "cost": finding.get("cost"),
            },
        }
        if len(sources) > 1:
            result["relatedLocations"] = [location(item, index) for index, item in enumerate(sources[1:10], start=1)]
        results.append(result)

    category_id = category.strip("/") + "/"
    sarif = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "frontend-system-review",
                        "version": "2.0.0",
                        "informationUri": "https://github.com/oasis-tcs/sarif-spec",
                        "rules": rules,
                    }
                },
                "automationDetails": {"id": category_id},
                "originalUriBaseIds": {"%SRCROOT%": {"uri": "./"}},
                "results": results,
                "columnKind": "utf16CodeUnits",
            }
        ],
    }
    return sarif, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Review JSON")
    parser.add_argument("--output", type=Path, required=True, help="Write SARIF to this path")
    parser.add_argument("--include-likely", action="store_true", help="Include likely findings; default is confirmed only")
    parser.add_argument("--category", default="frontend-system-review", help="Stable GitHub analysis category")
    args = parser.parse_args()
    try:
        report = load_json(args.report)
        if not isinstance(report, dict):
            raise ValueError("report must be a JSON object")
        sarif, skipped = to_sarif(report, args.include_likely, args.category)
        save_json(args.output, sarif)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    exported = len(sarif["runs"][0]["results"])
    print(json.dumps({"ok": True, "output": str(args.output), "exported": exported, "skipped": skipped}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
