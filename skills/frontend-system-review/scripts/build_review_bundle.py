#!/usr/bin/env python3
"""Build a verified review bundle with Markdown, SARIF, gate, diff, and hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from compare_reports import compare_reports
from export_sarif import to_sarif
from gate_report import evaluate, merge_policy
from render_report import render
from review_common import load_json, save_json, tool_version
from score_report import calculate
from verify_findings import validate_report


SCRIPT_ROOT = Path(__file__).resolve().parent
ENGINE_FILES = (
    "build_review_bundle.py",
    "compare_reports.py",
    "export_sarif.py",
    "gate_report.py",
    "render_report.py",
    "review_common.py",
    "score_report.py",
    "verify_findings.py",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Source review JSON")
    parser.add_argument("--repo", type=Path, required=True, help="Repository root for source evidence")
    parser.add_argument("--output", type=Path, required=True, help="Bundle output directory")
    parser.add_argument("--artifact-root", type=Path, help="Evidence artifact root; defaults to output")
    parser.add_argument("--baseline", type=Path, help="Accepted baseline review JSON")
    parser.add_argument("--policy", type=Path, help="Gate policy JSON")
    parser.add_argument("--include-likely-sarif", action="store_true", help="Include likely source findings in SARIF")
    parser.add_argument("--require-all-scores", action="store_true", help="Require all scoring dimensions when scoring exists")
    args = parser.parse_args()

    try:
        input_hashes = {
            "report_sha256": sha256_file(args.report),
            "baseline_sha256": sha256_file(args.baseline) if args.baseline else None,
            "policy_sha256": sha256_file(args.policy) if args.policy else None,
        }
        source_report = load_json(args.report)
        if not isinstance(source_report, dict):
            raise ValueError("report must be a JSON object")
        baseline = load_json(args.baseline) if args.baseline else None
        raw_policy = load_json(args.policy) if args.policy else None
        if baseline is not None and not isinstance(baseline, dict):
            raise ValueError("baseline must be a JSON object")
        if raw_policy is not None and not isinstance(raw_policy, dict):
            raise ValueError("policy must be a JSON object")
        repo = args.repo.resolve()
        if not repo.is_dir():
            raise ValueError(f"repository does not exist: {repo}")
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=True)
        artifact_root = (args.artifact_root or output).resolve()
        if not artifact_root.is_dir():
            raise ValueError(f"artifact root does not exist: {artifact_root}")

        report = json.loads(json.dumps(source_report))
        if isinstance(report.get("scoring"), dict):
            report["scoring"]["result"] = calculate(report["scoring"], args.require_all_scores)
        review_path = output / "review.json"
        save_json(review_path, report)

        errors, warnings = validate_report(report, repo, artifact_root, strict=True)
        validation_path = output / "verification.json"
        save_json(validation_path, {"valid": not errors, "errors": errors, "warnings": warnings})
        if errors:
            print(json.dumps({"ok": False, "stage": "verification", "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
            return 1

        markdown_path = output / "review.md"
        write_text(markdown_path, render(report))
        sarif, sarif_skipped = to_sarif(report, args.include_likely_sarif, "frontend-system-review")
        sarif_path = output / "review.sarif"
        save_json(sarif_path, sarif)

        diff = compare_reports(baseline, report) if baseline else None
        if diff:
            save_json(output / "baseline-diff.json", diff)

        policy = merge_policy(raw_policy)
        gate = evaluate(report, policy, baseline)
        gate_path = output / "gate-result.json"
        save_json(gate_path, gate)

        produced = [review_path, validation_path, markdown_path, sarif_path, gate_path]
        if diff:
            produced.append(output / "baseline-diff.json")
        manifest: dict[str, Any] = {
            "schema_version": "review-bundle-1.0",
            "tool": {
                "name": "frontend-system-review",
                "version": tool_version(),
                "engine_sha256": {name: sha256_file(SCRIPT_ROOT / name) for name in ENGINE_FILES},
            },
            "inputs": input_hashes,
            "configuration": {
                "strict": True,
                "include_likely_sarif": args.include_likely_sarif,
                "require_all_scores": args.require_all_scores,
                "baseline_used": baseline is not None,
                "policy_evaluation": policy["evaluation"],
            },
            "summary": {
                "findings": len(report.get("findings", [])),
                "sarif_exported": len(sarif["runs"][0]["results"]),
                "sarif_skipped": sarif_skipped,
                "gate_passed": gate["passed"],
                "verification_warnings": len(warnings),
            },
            "files": [
                {
                    "path": path.relative_to(output).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in sorted(produced)
            ],
        }
        manifest_path = output / "manifest.json"
        save_json(manifest_path, manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "stage": "input_or_build", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    print(
        json.dumps(
            {
                "ok": gate["passed"],
                "output": str(output),
                "gate_passed": gate["passed"],
                "files": len(manifest["files"]) + 1,
                "sarif_exported": manifest["summary"]["sarif_exported"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
