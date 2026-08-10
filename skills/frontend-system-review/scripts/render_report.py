#!/usr/bin/env python3
"""Render a frontend-system-review JSON report as deterministic Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from review_common import finding_fingerprint, load_json


CONCLUSION_LABELS = {
    "block": "阻断上线/合并",
    "ready_after_fixes": "修复后可上线/合并",
    "ready_with_followups": "可上线/合并但需跟进",
    "acceptable": "可接受",
    "unable_to_determine": "无法判断",
}
CONFIDENCE_LABELS = {"high": "高置信度", "medium": "中置信度", "low": "低置信度"}
SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}


def evidence_location(item: dict[str, Any]) -> str:
    if item.get("kind") == "source" and item.get("file"):
        line = item.get("line")
        end_line = item.get("end_line")
        if line and end_line and end_line != line:
            return f"`{item['file']}:{line}-{end_line}`"
        if line:
            return f"`{item['file']}:{line}`"
        return f"`{item['file']}`"
    if item.get("url"):
        suffix = f" ({item['viewport']})" if item.get("viewport") else ""
        return f"{item['url']}{suffix}"
    if item.get("artifact"):
        return f"`{item['artifact']}`"
    return "未提供位置"


def render(report: dict[str, Any]) -> str:
    review = report.get("review", {})
    lines = [f"# {review.get('title', '前端系统评审报告')}", ""]
    lines.extend(
        [
            "## 执行摘要",
            "",
            f"- 评审对象：{review.get('target', '')}",
            f"- 模式与深度：{review.get('mode', '')} / {review.get('depth', '')}",
            f"- 结论：{CONCLUSION_LABELS.get(review.get('conclusion'), review.get('conclusion', ''))}",
            f"- 判断：{review.get('summary', '')}",
            "",
            "## 范围与限制",
            "",
        ]
    )
    scope = review.get("scope", {})
    for key, label in (("checked", "已检查"), ("unchecked", "未检查"), ("assumptions", "关键假设")):
        values = scope.get(key, []) if isinstance(scope, dict) else []
        rendered = "；".join(str(value) for value in values) if values else "无"
        lines.append(f"- {label}：{rendered}")

    lines.extend(["", "## Findings", ""])
    findings = sorted(
        report.get("findings", []),
        key=lambda item: (SEVERITY_ORDER.get(item.get("severity"), 9), item.get("id", "")),
    )
    if not findings:
        lines.extend(["未发现可报告问题。", ""])
    for finding in findings:
        confidence = CONFIDENCE_LABELS.get(finding.get("confidence"), finding.get("confidence", ""))
        lines.extend(
            [
                f"### [{finding.get('severity', '')}][{confidence}] {finding.get('id', '')} — {finding.get('title', '')}",
                "",
                f"- 维度：{finding.get('dimension', '')}",
                f"- 状态：{finding.get('status', '')}",
                f"- 指纹：`{finding_fingerprint(finding)}`",
            ]
        )
        for item in finding.get("evidence", []):
            lines.append(f"- 证据：{evidence_location(item)} — {item.get('summary', '')}")
        lines.append(f"- 影响：{finding.get('impact', '')}")
        if finding.get("root_cause"):
            lines.append(f"- 根因：{finding['root_cause']}")
        lines.append(f"- 修复：{finding.get('fix', '')}")
        for verification in finding.get("verification", []):
            lines.append(f"- 验证：{verification}")
        if finding.get("cost"):
            lines.append(f"- 预计成本：{finding['cost']}")
        lines.append("")

    lines.extend(["## 未验证风险", ""])
    risks = report.get("unverified_risks", [])
    if risks:
        lines.extend(["| 事项 | 为什么重要 | 当前缺口 | 如何验证 |", "|---|---|---|---|"])
        for risk in risks:
            row = [risk.get("title", ""), risk.get("importance", ""), risk.get("gap", ""), risk.get("verification", "")]
            lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    else:
        lines.append("无。")
    lines.append("")

    scoring = report.get("scoring", {})
    result = scoring.get("result") if isinstance(scoring, dict) else None
    if isinstance(result, dict):
        lines.extend(
            [
                "## 评分",
                "",
                f"- 总分：{result.get('total')}/100",
                f"- 等级：{result.get('grade')}",
                f"- 证据覆盖率：{result.get('evidence_coverage')}%",
                f"- 状态：{result.get('status')}",
                "",
            ]
        )

    strengths = report.get("strengths", [])
    if strengths:
        lines.extend(["## 已验证的优点", ""])
        for item in strengths:
            lines.append(f"- {item.get('summary', '')} — {item.get('evidence', '')}")
        lines.append("")

    lines.extend(["## 验证记录", ""])
    validation = report.get("validation", [])
    if validation:
        lines.extend(["| 检查 | 结果 | 命令或步骤 | 说明 |", "|---|---|---|---|"])
        for item in validation:
            row = [item.get("check", ""), item.get("result", ""), item.get("command_or_steps", ""), item.get("notes", "")]
            lines.append("| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |")
    else:
        lines.append("未记录验证。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Path to review JSON")
    parser.add_argument("--output", type=Path, help="Write Markdown to this path; stdout when omitted")
    args = parser.parse_args()
    try:
        report = load_json(args.report)
        if not isinstance(report, dict):
            raise ValueError("report root must be an object")
        markdown = render(report)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(markdown, encoding="utf-8", newline="\n")
        else:
            print(markdown)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
