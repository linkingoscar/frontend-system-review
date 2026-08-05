#!/usr/bin/env python3
"""Verify review-bundle hashes and optionally revalidate evidence and gate status."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from review_common import is_within, load_json
from verify_findings import validate_report


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Review bundle directory")
    parser.add_argument("--repo", type=Path, help="Revalidate review source evidence against this repository")
    parser.add_argument("--artifact-root", type=Path, help="Artifact root for evidence; defaults to bundle")
    parser.add_argument("--require-gate-pass", action="store_true", help="Fail when gate-result.json is not passed")
    args = parser.parse_args()

    bundle = args.bundle.resolve()
    if not bundle.is_dir():
        print(json.dumps({"valid": False, "errors": [f"bundle does not exist: {bundle}"]}, ensure_ascii=False, indent=2))
        return 2
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_json(bundle / "manifest.json")
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "review-bundle-1.0":
            raise ValueError("manifest.json is not a review-bundle-1.0 manifest")
        entries = manifest.get("files")
        if not isinstance(entries, list):
            raise ValueError("manifest.files must be an array")
        seen: set[str] = set()
        for index, entry in enumerate(entries):
            label = f"manifest.files[{index}]"
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                errors.append(f"{label}: invalid entry")
                continue
            relative = entry["path"]
            if relative in seen:
                errors.append(f"{label}: duplicate path {relative}")
                continue
            seen.add(relative)
            candidate = (bundle / relative).resolve()
            if not is_within(candidate, bundle):
                errors.append(f"{label}: path escapes bundle: {relative}")
                continue
            if not candidate.is_file():
                errors.append(f"{label}: missing file {relative}")
                continue
            actual_size = candidate.stat().st_size
            actual_hash = sha256_file(candidate)
            if entry.get("bytes") != actual_size:
                errors.append(f"{label}: size mismatch for {relative}")
            if entry.get("sha256") != actual_hash:
                errors.append(f"{label}: SHA-256 mismatch for {relative}")
        required = {"review.json", "review.md", "review.sarif", "verification.json", "gate-result.json"}
        if manifest.get("configuration", {}).get("baseline_used"):
            required.add("baseline-diff.json")
        for missing in sorted(required - seen):
            errors.append(f"manifest.files: required bundle file is not listed: {missing}")

        if args.repo:
            repo = args.repo.resolve()
            if not repo.is_dir():
                raise ValueError(f"repository does not exist: {repo}")
            report = load_json(bundle / "review.json")
            artifact_root = (args.artifact_root or bundle).resolve()
            evidence_errors, evidence_warnings = validate_report(report, repo, artifact_root, strict=True)
            errors.extend(f"review: {item}" for item in evidence_errors)
            warnings.extend(f"review: {item}" for item in evidence_warnings)
        elif args.artifact_root:
            raise ValueError("--artifact-root requires --repo")

        if args.require_gate_pass:
            gate = load_json(bundle / "gate-result.json")
            if not isinstance(gate, dict) or gate.get("passed") is not True:
                errors.append("gate-result.json: gate did not pass")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)], "warnings": warnings}, ensure_ascii=False, indent=2))
        return 2

    print(
        json.dumps(
            {
                "valid": not errors,
                "checked_files": len(manifest.get("files", [])),
                "evidence_revalidated": bool(args.repo),
                "gate_required": args.require_gate_pass,
                "errors": errors,
                "warnings": warnings,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
