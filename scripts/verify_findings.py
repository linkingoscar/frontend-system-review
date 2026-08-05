#!/usr/bin/env python3
"""Validate machine-readable findings and verify source citations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

from review_common import (
    CONCLUSIONS,
    CONFIDENCES,
    DEPTHS,
    DIMENSIONS,
    FINDING_STATUSES,
    MODES,
    SCHEMA_VERSION,
    SEVERITIES,
    finding_fingerprint,
    is_within,
    load_json,
    normalize_whitespace,
)
from score_report import calculate


def require_string(container: dict[str, Any], key: str, path: str, errors: list[str]) -> None:
    if not isinstance(container.get(key), str) or not container[key].strip():
        errors.append(f"{path}.{key}: expected a non-empty string")


def validate_source_evidence(
    evidence: dict[str, Any],
    label: str,
    repo: Path,
    strict: bool,
    errors: list[str],
    warnings: list[str],
) -> None:
    file_value = evidence.get("file")
    line = evidence.get("line")
    if not isinstance(file_value, str) or not file_value.strip():
        errors.append(f"{label}.file: source evidence requires a relative file path")
        return
    if isinstance(line, bool) or not isinstance(line, int) or line < 1:
        errors.append(f"{label}.line: source evidence requires a positive line number")
        return

    candidate = (repo / file_value).resolve()
    if not is_within(candidate, repo):
        errors.append(f"{label}.file: path escapes repository root: {file_value}")
        return
    if not candidate.is_file():
        errors.append(f"{label}.file: file does not exist: {file_value}")
        return

    try:
        lines = candidate.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError as exc:
        errors.append(f"{label}.file: cannot read {file_value}: {exc}")
        return

    end_line = evidence.get("end_line", line)
    if isinstance(end_line, bool) or not isinstance(end_line, int) or end_line < line:
        errors.append(f"{label}.end_line: must be an integer greater than or equal to line")
        return
    if end_line > len(lines):
        errors.append(
            f"{label}: cited lines {line}-{end_line} exceed {file_value} line count {len(lines)}"
        )
        return

    quote = evidence.get("quote")
    if strict and (not isinstance(quote, str) or not quote.strip()):
        errors.append(f"{label}.quote: strict mode requires a source quote")
    elif isinstance(quote, str) and quote.strip():
        selected = normalize_whitespace("\n".join(lines[line - 1 : end_line]))
        normalized_quote = normalize_whitespace(quote)
        if normalized_quote not in selected:
            errors.append(f"{label}.quote: quote does not match cited lines in {file_value}")
    else:
        warnings.append(f"{label}.quote: no quote supplied; line exists but claim was not text-matched")


def validate_tool_artifact(
    artifact_path: Path,
    label: str,
    artifact_root: Path,
    errors: list[str],
    warnings: list[str],
) -> None:
    if artifact_path.suffix.casefold() != ".json":
        warnings.append(f"{label}: tool artifact is not command-evidence-1.0; completeness and provenance were not mechanically checked")
        return
    try:
        metadata = load_json(artifact_path)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label}: cannot parse tool artifact JSON: {exc}")
        return
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "command-evidence-1.0":
        warnings.append(f"{label}: tool artifact is not command-evidence-1.0; completeness and provenance were not mechanically checked")
        return
    if not isinstance(metadata.get("command"), list) or not metadata["command"]:
        errors.append(f"{label}: command evidence has no command array")
    if metadata.get("exit_code") is not None and (
        isinstance(metadata.get("exit_code"), bool) or not isinstance(metadata.get("exit_code"), int)
    ):
        errors.append(f"{label}: command evidence exit_code must be an integer or null")
    capture = metadata.get("capture")
    if not isinstance(capture, dict) or not isinstance(capture.get("complete"), bool):
        errors.append(f"{label}: command evidence capture.complete must be boolean")
    elif not capture["complete"]:
        warnings.append(f"{label}: command capture is incomplete")
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append(f"{label}: command evidence has no artifacts object")
        return
    for stream in ("stdout", "stderr"):
        entry = artifacts.get(stream)
        stream_label = f"{label}.{stream}"
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            errors.append(f"{stream_label}: missing artifact path")
            continue
        candidate = (artifact_path.parent / entry["path"]).resolve()
        if not is_within(candidate, artifact_root):
            errors.append(f"{stream_label}: path escapes artifact root")
            continue
        if not candidate.is_file():
            errors.append(f"{stream_label}: file does not exist: {entry['path']}")
            continue
        if entry.get("bytes") != candidate.stat().st_size:
            errors.append(f"{stream_label}: byte count mismatch")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            errors.append(f"{stream_label}: SHA-256 mismatch")


def validate_report(
    report: Any,
    repo: Path,
    artifact_root: Path | None,
    strict: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(report, dict):
        return ["root: expected a JSON object"], warnings
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version: expected {SCHEMA_VERSION!r}")

    review = report.get("review")
    if not isinstance(review, dict):
        errors.append("review: expected an object")
    else:
        for key in ("title", "target", "summary"):
            require_string(review, key, "review", errors)
        if review.get("mode") not in MODES:
            errors.append(f"review.mode: expected one of {sorted(MODES)}")
        if review.get("depth") not in DEPTHS:
            errors.append(f"review.depth: expected one of {sorted(DEPTHS)}")
        if review.get("conclusion") not in CONCLUSIONS:
            errors.append(f"review.conclusion: expected one of {sorted(CONCLUSIONS)}")
        scope = review.get("scope")
        if not isinstance(scope, dict):
            errors.append("review.scope: expected an object")
        else:
            for key in ("checked", "unchecked", "assumptions"):
                if not isinstance(scope.get(key), list) or not all(
                    isinstance(value, str) for value in scope.get(key, [])
                ):
                    errors.append(f"review.scope.{key}: expected an array of strings")

    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append("findings: expected an array")
        findings = []

    ids: set[str] = set()
    fingerprints: dict[str, str] = {}
    normalized_titles: set[str] = set()
    has_confirmed_p0 = False
    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not isinstance(finding, dict):
            errors.append(f"{label}: expected an object")
            continue

        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not re.fullmatch(r"F-\d{3,}", finding_id):
            errors.append(f"{label}.id: expected F- followed by at least three digits")
        elif finding_id in ids:
            errors.append(f"{label}.id: duplicate id {finding_id}")
        else:
            ids.add(finding_id)

        fingerprint = finding.get("fingerprint")
        if fingerprint is not None and (
            not isinstance(fingerprint, str)
            or not re.fullmatch(r"[A-Za-z0-9._:-]{8,128}", fingerprint)
        ):
            errors.append(f"{label}.fingerprint: expected 8-128 URL-safe identity characters")
        else:
            logical_fingerprint = finding_fingerprint(finding)
            if logical_fingerprint in fingerprints:
                errors.append(
                    f"{label}.fingerprint: duplicate logical fingerprint {logical_fingerprint} "
                    f"also used by {fingerprints[logical_fingerprint]}"
                )
            else:
                fingerprints[logical_fingerprint] = str(finding_id or label)

        severity = finding.get("severity")
        confidence = finding.get("confidence")
        status = finding.get("status")
        if severity not in SEVERITIES:
            errors.append(f"{label}.severity: expected one of {sorted(SEVERITIES)}")
        if confidence not in CONFIDENCES:
            errors.append(f"{label}.confidence: expected one of {sorted(CONFIDENCES)}")
        if status not in FINDING_STATUSES:
            errors.append(f"{label}.status: expected one of {sorted(FINDING_STATUSES)}")
        if severity == "P0" and (confidence != "high" or status != "confirmed"):
            errors.append(f"{label}: P0 requires high confidence and confirmed status")
        if severity == "P0" and confidence == "high" and status == "confirmed":
            has_confirmed_p0 = True

        for key in ("dimension", "title", "impact", "fix"):
            require_string(finding, key, label, errors)
        if finding.get("dimension") not in DIMENSIONS:
            errors.append(f"{label}.dimension: expected one of {sorted(DIMENSIONS)}")
        if finding.get("cost") is not None and finding.get("cost") not in {"S", "M", "L", "unknown"}:
            errors.append(f"{label}.cost: expected S, M, L, or unknown")

        title = finding.get("title")
        if isinstance(title, str):
            normalized_title = normalize_whitespace(title).casefold()
            if normalized_title in normalized_titles:
                warnings.append(f"{label}.title: possible duplicate finding title")
            normalized_titles.add(normalized_title)

        verification = finding.get("verification")
        if not isinstance(verification, list) or not verification or not all(
            isinstance(value, str) and value.strip() for value in verification
        ):
            errors.append(f"{label}.verification: expected a non-empty array of strings")

        evidence_list = finding.get("evidence")
        if not isinstance(evidence_list, list) or not evidence_list:
            errors.append(f"{label}.evidence: expected at least one evidence item")
            continue
        for evidence_index, evidence in enumerate(evidence_list):
            evidence_label = f"{label}.evidence[{evidence_index}]"
            if not isinstance(evidence, dict):
                errors.append(f"{evidence_label}: expected an object")
                continue
            kind = evidence.get("kind")
            if kind not in {"source", "runtime", "tool", "inference"}:
                errors.append(f"{evidence_label}.kind: unsupported evidence kind")
            require_string(evidence, "summary", evidence_label, errors)
            if kind == "source":
                validate_source_evidence(evidence, evidence_label, repo, strict, errors, warnings)
            elif kind == "runtime":
                if not isinstance(evidence.get("url"), str) or not evidence["url"].strip():
                    errors.append(f"{evidence_label}.url: runtime evidence requires a URL")
                if strict and (not isinstance(evidence.get("artifact"), str) or not evidence["artifact"].strip()):
                    errors.append(f"{evidence_label}.artifact: strict mode requires a runtime artifact")
                if strict and artifact_root is None:
                    errors.append(f"{evidence_label}.artifact: strict runtime verification requires --artifact-root")
            elif kind == "tool":
                if strict and (not isinstance(evidence.get("artifact"), str) or not evidence["artifact"].strip()):
                    errors.append(f"{evidence_label}.artifact: strict mode requires a tool-output artifact")
                if strict and artifact_root is None:
                    errors.append(f"{evidence_label}.artifact: strict tool verification requires --artifact-root")
            artifact = evidence.get("artifact")
            if artifact_root and isinstance(artifact, str) and artifact:
                artifact_path = (artifact_root / artifact).resolve()
                if not is_within(artifact_path, artifact_root):
                    errors.append(f"{evidence_label}.artifact: path escapes artifact root")
                elif not artifact_path.exists():
                    errors.append(f"{evidence_label}.artifact: artifact does not exist: {artifact}")
                elif kind == "tool" and strict:
                    validate_tool_artifact(artifact_path, evidence_label, artifact_root, errors, warnings)
        source_files = {
            str(item.get("file"))
            for item in evidence_list
            if isinstance(item, dict) and item.get("kind") == "source" and item.get("file")
        }
        if (
            strict
            and status == "confirmed"
            and len(source_files) > 1
            and all(isinstance(item, dict) and item.get("kind") == "source" for item in evidence_list)
        ):
            warnings.append(
                f"{label}: cross-file source citations are text-matched, but semantic reachability "
                "still requires an independently checked call/configuration path or runtime reproduction"
            )

    if has_confirmed_p0 and isinstance(review, dict) and review.get("conclusion") != "block":
        errors.append("review.conclusion: confirmed P0 requires block")

    risks = report.get("unverified_risks")
    if not isinstance(risks, list):
        errors.append("unverified_risks: expected an array")
    else:
        for index, risk in enumerate(risks):
            label = f"unverified_risks[{index}]"
            if not isinstance(risk, dict):
                errors.append(f"{label}: expected an object")
                continue
            for key in ("title", "importance", "gap", "verification"):
                require_string(risk, key, label, errors)

    strengths = report.get("strengths", [])
    if not isinstance(strengths, list):
        errors.append("strengths: expected an array when present")
    else:
        for index, strength in enumerate(strengths):
            label = f"strengths[{index}]"
            if not isinstance(strength, dict):
                errors.append(f"{label}: expected an object")
                continue
            require_string(strength, "summary", label, errors)
            require_string(strength, "evidence", label, errors)

    scoring = report.get("scoring")
    if scoring is not None:
        if not isinstance(scoring, dict):
            errors.append("scoring: expected an object when present")
        else:
            try:
                calculated_scoring = calculate(scoring, require_all=False)
                stored_result = scoring.get("result")
                if stored_result is not None and stored_result != calculated_scoring:
                    errors.append("scoring.result: stored result does not match deterministic recalculation")
            except ValueError as exc:
                errors.append(f"scoring: {exc}")

    validation = report.get("validation")
    if not isinstance(validation, list):
        errors.append("validation: expected an array")
    else:
        for index, item in enumerate(validation):
            label = f"validation[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{label}: expected an object")
                continue
            require_string(item, "check", label, errors)
            if item.get("result") not in {"passed", "failed", "not_run", "partial"}:
                errors.append(f"{label}.result: unsupported validation result")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to review JSON")
    parser.add_argument("--repo", type=Path, required=True, help="Repository root for source citations")
    parser.add_argument("--artifact-root", type=Path, help="Root used to validate artifact paths")
    parser.add_argument("--strict", action="store_true", help="Require source quotes for deterministic matching")
    args = parser.parse_args()

    try:
        report = load_json(args.report)
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 2

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(json.dumps({"valid": False, "errors": [f"repository does not exist: {repo}"], "warnings": []}, ensure_ascii=False, indent=2))
        return 2

    errors, warnings = validate_report(
        report,
        repo,
        args.artifact_root.resolve() if args.artifact_root else None,
        args.strict,
    )
    result = {"valid": not errors, "errors": errors, "warnings": warnings}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
