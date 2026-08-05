#!/usr/bin/env python3
"""Evaluate a review report against a deterministic release-gate policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from compare_reports import compare_reports, index_findings
from review_common import load_json, save_json
from score_report import calculate


DEFAULT_POLICY: dict[str, Any] = {
    "policy_version": "1.0",
    "evaluation": "all",
    "block_conclusions": ["block", "ready_after_fixes", "unable_to_determine"],
    "block_on": [{"severities": ["P0"], "statuses": ["confirmed"]}],
    "max_counts": {},
    "scoring": {
        "min_total": None,
        "min_evidence_coverage": None,
        "require_final": False,
    },
    "max_unverified_risks": None,
    "require_validation_passed": False,
}


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("policy_version") != "1.0":
        raise ValueError("policy_version must be '1.0'")
    if policy.get("evaluation") not in {"all", "new", "new_or_regressed"}:
        raise ValueError("evaluation must be all, new, or new_or_regressed")
    if not isinstance(policy.get("block_conclusions", []), list):
        raise ValueError("block_conclusions must be an array")
    rules = policy.get("block_on", [])
    if not isinstance(rules, list):
        raise ValueError("block_on must be an array")
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"block_on[{index}] must be an object")
        severities = rule.get("severities")
        statuses = rule.get("statuses")
        if not isinstance(severities, list) or not severities or not set(severities) <= {"P0", "P1", "P2"}:
            raise ValueError(f"block_on[{index}].severities is invalid")
        if not isinstance(statuses, list) or not statuses or not set(statuses) <= {"confirmed", "likely"}:
            raise ValueError(f"block_on[{index}].statuses is invalid")
    max_counts = policy.get("max_counts", {})
    if not isinstance(max_counts, dict) or not set(max_counts) <= {"P0", "P1", "P2"}:
        raise ValueError("max_counts keys must be P0, P1, or P2")
    for severity, value in max_counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"max_counts.{severity} must be a non-negative integer")
    scoring = policy.get("scoring", {})
    if not isinstance(scoring, dict):
        raise ValueError("scoring must be an object")
    for key in ("min_total", "min_evidence_coverage"):
        value = scoring.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100):
            raise ValueError(f"scoring.{key} must be null or a number from 0 to 100")
    risk_limit = policy.get("max_unverified_risks")
    if risk_limit is not None and (isinstance(risk_limit, bool) or not isinstance(risk_limit, int) or risk_limit < 0):
        raise ValueError("max_unverified_risks must be null or a non-negative integer")


def merge_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    policy = json.loads(json.dumps(DEFAULT_POLICY))
    if raw:
        for key, value in raw.items():
            if key == "scoring" and isinstance(value, dict):
                policy["scoring"].update(value)
            else:
                policy[key] = value
    validate_policy(policy)
    return policy


def evaluated_findings(
    report: dict[str, Any], policy: dict[str, Any], baseline: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    findings = report.get("findings")
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ValueError("report.findings must be an array of objects")
    if policy["evaluation"] == "all":
        return list(findings), None
    if baseline is None:
        raise ValueError(f"policy evaluation '{policy['evaluation']}' requires --baseline")

    diff = compare_reports(baseline, report)
    current_by_fingerprint = index_findings(report, "current")
    fingerprints = {item["fingerprint"] for item in diff["new"]}
    if policy["evaluation"] == "new_or_regressed":
        fingerprints.update(item["fingerprint"] for item in diff["changed"] if item["regression"])
    return [current_by_fingerprint[key] for key in sorted(fingerprints)], diff


def evaluate(
    report: dict[str, Any], policy: dict[str, Any], baseline: dict[str, Any] | None
) -> dict[str, Any]:
    findings, diff = evaluated_findings(report, policy, baseline)
    reasons: list[dict[str, Any]] = []
    review = report.get("review") if isinstance(report.get("review"), dict) else {}
    conclusion = review.get("conclusion")
    if conclusion in policy["block_conclusions"]:
        reasons.append({"code": "blocked_conclusion", "message": f"review conclusion is {conclusion}"})

    counts = {severity: sum(1 for item in findings if item.get("severity") == severity) for severity in ("P0", "P1", "P2")}
    for finding in findings:
        for rule in policy["block_on"]:
            if finding.get("severity") in rule["severities"] and finding.get("status") in rule["statuses"]:
                reasons.append(
                    {
                        "code": "blocking_finding",
                        "finding_id": finding.get("id"),
                        "severity": finding.get("severity"),
                        "status": finding.get("status"),
                        "message": finding.get("title"),
                    }
                )
                break
    for severity, maximum in policy["max_counts"].items():
        if counts[severity] > maximum:
            reasons.append(
                {
                    "code": "finding_count_exceeded",
                    "severity": severity,
                    "actual": counts[severity],
                    "maximum": maximum,
                }
            )

    scoring_policy = policy["scoring"]
    if any(scoring_policy.get(key) is not None for key in ("min_total", "min_evidence_coverage")) or scoring_policy.get("require_final"):
        scoring = report.get("scoring")
        if not isinstance(scoring, dict):
            reasons.append({"code": "scoring_missing", "message": "policy requires scoring"})
            score_result = None
        else:
            score_result = scoring.get("result")
            if not isinstance(score_result, dict):
                try:
                    score_result = calculate(scoring, require_all=False)
                except ValueError as exc:
                    reasons.append({"code": "scoring_invalid", "message": str(exc)})
                    score_result = None
        if score_result:
            for policy_key, result_key in (("min_total", "total"), ("min_evidence_coverage", "evidence_coverage")):
                minimum = scoring_policy.get(policy_key)
                if minimum is not None and score_result.get(result_key, -1) < minimum:
                    reasons.append(
                        {
                            "code": f"{result_key}_below_minimum",
                            "actual": score_result.get(result_key),
                            "minimum": minimum,
                        }
                    )
            if scoring_policy.get("require_final") and score_result.get("status") != "final":
                reasons.append({"code": "scoring_not_final", "actual": score_result.get("status")})

    risks = report.get("unverified_risks")
    risk_count = len(risks) if isinstance(risks, list) else 0
    risk_limit = policy.get("max_unverified_risks")
    if risk_limit is not None and risk_count > risk_limit:
        reasons.append({"code": "unverified_risk_count_exceeded", "actual": risk_count, "maximum": risk_limit})

    if policy.get("require_validation_passed"):
        validation = report.get("validation")
        invalid = [item for item in validation or [] if not isinstance(item, dict) or item.get("result") != "passed"]
        if not isinstance(validation, list) or invalid:
            reasons.append({"code": "validation_incomplete", "non_passing_checks": len(invalid)})

    return {
        "schema_version": "review-gate-1.0",
        "passed": not reasons,
        "evaluation": policy["evaluation"],
        "evaluated_findings": len(findings),
        "counts": counts,
        "unverified_risks": risk_count,
        "reasons": reasons,
        "baseline_diff_summary": diff["summary"] if diff else None,
        "policy": policy,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Current review JSON")
    parser.add_argument("--policy", type=Path, help="JSON policy; built-in P0 policy when omitted")
    parser.add_argument("--baseline", type=Path, help="Baseline review for incremental policies")
    parser.add_argument("--output", type=Path, help="Write gate result JSON to this path")
    args = parser.parse_args()

    try:
        report = load_json(args.report)
        raw_policy = load_json(args.policy) if args.policy else None
        baseline = load_json(args.baseline) if args.baseline else None
        if not isinstance(report, dict):
            raise ValueError("report must be a JSON object")
        if raw_policy is not None and not isinstance(raw_policy, dict):
            raise ValueError("policy must be a JSON object")
        if baseline is not None and not isinstance(baseline, dict):
            raise ValueError("baseline must be a JSON object")
        policy = merge_policy(raw_policy)
        result = evaluate(report, policy, baseline)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    if args.output:
        save_json(args.output, result)
    print(json.dumps({"ok": True, **{key: result[key] for key in ("passed", "evaluation", "evaluated_findings", "counts", "reasons")}}, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
