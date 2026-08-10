#!/usr/bin/env python3
"""Collect deterministic changed-file and changed-line scope for frontend reviews."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from review_common import save_json


HUNK = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_count>\d+))? \+(?P<new>\d+)(?:,(?P<new_count>\d+))? @@")
RISK_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(?:^|/)(?:package\.json|[^/]*lock[^/]*|pnpm-workspace\.yaml)$", re.I), "dependencies_build", "high"),
    (re.compile(r"(?:^|/)(?:\.github/workflows|\.gitlab-ci|ci|deploy|docker|vercel|netlify)(?:/|\.|$)", re.I), "ci_release", "high"),
    (re.compile(r"(?:^|/)(?:auth|security|permission|rbac|session|token|oauth)(?:/|\.|-|$)", re.I), "auth_security", "high"),
    (re.compile(r"(?:^|/)(?:api|schema|contract|types?)(?:/|\.|-|$)", re.I), "api_contract", "high"),
    (re.compile(r"(?:^|/)(?:routes?|pages?|app)(?:/|\.|-|$)", re.I), "routing_rendering", "medium"),
    (re.compile(r"(?:^|/)(?:shared|components?|design-system|ui)(?:/|\.|-|$)", re.I), "shared_ui", "medium"),
    (re.compile(r"(?:^|/)(?:tests?|__tests__|e2e|playwright|cypress)(?:/|\.|-|$)", re.I), "tests", "low"),
    (re.compile(r"(?:^|/)(?:\.env|config|tsconfig|eslint|vite|webpack|next\.config)(?:\.|/|$)", re.I), "configuration", "high"),
]


def strip_prefix(value: str) -> str:
    value = value.strip()
    if value == "/dev/null":
        return value
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        try:
            value = shlex.split(value)[0]
        except ValueError:
            value = value[1:-1]
    return value[2:] if value.startswith(("a/", "b/")) else value


def parse_diff(diff: str) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            try:
                parts = shlex.split(line)
                old_path, new_path = strip_prefix(parts[-2]), strip_prefix(parts[-1])
            except (ValueError, IndexError):
                old_path = new_path = line[len("diff --git ") :].strip()
            current = {
                "path": new_path,
                "old_path": old_path if old_path != new_path else None,
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "binary": False,
                "changed_lines": [],
            }
            continue
        if current is None:
            continue
        if line.startswith("new file mode "):
            current["status"] = "added"
        elif line.startswith("deleted file mode "):
            current["status"] = "deleted"
        elif line.startswith("rename from "):
            current["status"] = "renamed"
            current["old_path"] = line[len("rename from ") :]
        elif line.startswith("rename to "):
            current["path"] = line[len("rename to ") :]
        elif line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            current["binary"] = True
        elif line.startswith("+++ "):
            candidate = strip_prefix(line[4:])
            if candidate != "/dev/null":
                current["path"] = candidate
        elif line.startswith("--- "):
            candidate = strip_prefix(line[4:])
            if candidate != "/dev/null" and current.get("old_path") is None and candidate != current.get("path"):
                current["old_path"] = candidate
        else:
            match = HUNK.match(line)
            if match:
                start = int(match.group("new"))
                count = int(match.group("new_count") or 1)
                if count > 0:
                    current["changed_lines"].append({"start": start, "end": start + count - 1})
            elif line.startswith("+") and not line.startswith("+++"):
                current["additions"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                current["deletions"] += 1
    if current:
        files.append(current)
    return files


def classify(file: dict[str, Any]) -> None:
    path = str(file.get("path") or "")
    categories = []
    priority_rank = {"low": 1, "medium": 2, "high": 3}
    priority = "low"
    for pattern, category, rule_priority in RISK_RULES:
        if pattern.search(path):
            categories.append(category)
            if priority_rank[rule_priority] > priority_rank[priority]:
                priority = rule_priority
    churn = int(file.get("additions") or 0) + int(file.get("deletions") or 0)
    if churn >= 300 or file.get("binary"):
        priority = "high"
    elif churn >= 100 and priority == "low":
        priority = "medium"
    file["categories"] = categories
    file["review_priority"] = priority


def run_git(repo: Path, arguments: list[str]) -> str:
    command = ["git", "-c", "core.quotepath=false", "-C", str(repo), *arguments]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or f"git exited {result.returncode}")
    return result.stdout


def inspect_untracked(path: Path) -> tuple[int, bool]:
    line_count = 0
    has_data = False
    final_byte = b""
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                has_data = True
                final_byte = chunk[-1:]
                if b"\0" in chunk:
                    return 0, True
                line_count += chunk.count(b"\n")
    except OSError:
        return 0, True
    if has_data and final_byte != b"\n":
        line_count += 1
    return line_count, False


def add_untracked(repo: Path, files: list[dict[str, Any]]) -> None:
    output = run_git(repo, ["ls-files", "--others", "--exclude-standard", "-z"])
    known = {str(item.get("path")) for item in files}
    for value in output.split("\0"):
        if not value or value in known:
            continue
        path = repo / value
        if not path.is_file():
            continue
        line_count, binary = inspect_untracked(path)
        files.append(
            {
                "path": value.replace("\\", "/"),
                "old_path": None,
                "status": "added",
                "additions": line_count,
                "deletions": 0,
                "binary": binary,
                "changed_lines": [{"start": 1, "end": line_count}] if line_count else [],
            }
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path, help="Git repository root")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--base", help="Base revision; compares base...head")
    source.add_argument("--staged", action="store_true", help="Collect staged changes")
    source.add_argument("--working-tree", action="store_true", help="Collect unstaged and untracked changes (default)")
    source.add_argument("--diff-file", type=Path, help="Parse an existing unified diff instead of invoking git diff")
    parser.add_argument("--head", default="HEAD", help="Head revision used with --base")
    parser.add_argument("--output", type=Path, help="Write scope JSON to this path")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(json.dumps({"ok": False, "error": f"repository does not exist: {repo}"}, ensure_ascii=False, indent=2))
        return 2
    try:
        if args.diff_file:
            diff = args.diff_file.read_text(encoding="utf-8-sig")
            source_info = {"type": "diff_file", "path": str(args.diff_file)}
        elif args.base:
            diff = run_git(repo, ["diff", "--no-ext-diff", "--find-renames", "--unified=0", f"{args.base}...{args.head}", "--"])
            source_info = {"type": "revision_range", "base": args.base, "head": args.head}
        elif args.staged:
            diff = run_git(repo, ["diff", "--cached", "--no-ext-diff", "--find-renames", "--unified=0", "--"])
            source_info = {"type": "staged"}
        else:
            diff = run_git(repo, ["diff", "--no-ext-diff", "--find-renames", "--unified=0", "--"])
            source_info = {"type": "working_tree", "includes_untracked": True}
        files = parse_diff(diff)
        if not args.diff_file and not args.base and not args.staged:
            add_untracked(repo, files)
        for file in files:
            classify(file)
        files.sort(key=lambda item: ({"high": 0, "medium": 1, "low": 2}[item["review_priority"]], item["path"]))
    except (OSError, UnicodeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2

    category_counts: dict[str, int] = {}
    for file in files:
        for category in file["categories"]:
            category_counts[category] = category_counts.get(category, 0) + 1
    output = {
        "schema_version": "change-scope-1.0",
        "source": source_info,
        "summary": {
            "files": len(files),
            "additions": sum(int(item["additions"]) for item in files),
            "deletions": sum(int(item["deletions"]) for item in files),
            "high_priority_files": sum(item["review_priority"] == "high" for item in files),
            "categories": dict(sorted(category_counts.items())),
        },
        "files": files,
        "review_guidance": [
            "Review high-priority files first and follow their consumers beyond the changed lines.",
            "Use changed lines to establish scope, not to ignore affected contracts, tests, or runtime paths.",
            "Do not report pre-existing issues unless the change introduces, exposes, or materially worsens them.",
        ],
    }
    if args.output:
        save_json(args.output, output)
    print(json.dumps({"ok": True, **output["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
