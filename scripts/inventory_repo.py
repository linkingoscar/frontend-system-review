#!/usr/bin/env python3
"""Create a deterministic, non-judgmental inventory of a frontend repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from review_common import is_within, save_json


IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    ".nuxt",
    ".output",
    ".turbo",
    ".cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
}
TEXT_EXTENSIONS = {
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".html",
}
SOURCE_EXTENSIONS = TEXT_EXTENSIONS | {".less", ".sass"}
RISK_PATTERNS = {
    "dangerously_set_inner_html": re.compile(r"dangerouslySetInnerHTML"),
    "raw_inner_html": re.compile(r"\binnerHTML\s*="),
    "vue_raw_html": re.compile(r"\bv-html\b"),
    "dynamic_eval": re.compile(r"\beval\s*\("),
    "new_function": re.compile(r"\bnew\s+Function\s*\("),
    "outline_none": re.compile(r"outline\s*:\s*none", re.IGNORECASE),
    "transition_all": re.compile(r"transition(?:-property)?\s*:[^;]*\ball\b", re.IGNORECASE),
}
LIBRARY_GROUPS = {
    "server_state": {"@tanstack/react-query", "react-query", "swr", "@apollo/client", "urql"},
    "client_state": {"redux", "@reduxjs/toolkit", "zustand", "jotai", "mobx", "recoil", "pinia"},
    "http": {"axios", "ky", "superagent", "got"},
}
FRAMEWORK_PACKAGES = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "nuxt": "Nuxt",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit",
    "solid-js": "Solid",
    "astro": "Astro",
}
TOOL_PACKAGES = {
    "typescript": "TypeScript",
    "vite": "Vite",
    "webpack": "Webpack",
    "rollup": "Rollup",
    "turborepo": "Turborepo",
    "turbo": "Turborepo",
    "nx": "Nx",
    "vitest": "Vitest",
    "jest": "Jest",
    "@playwright/test": "Playwright Test",
    "cypress": "Cypress",
    "eslint": "ESLint",
    "prettier": "Prettier",
    "storybook": "Storybook",
    "@storybook/react": "Storybook",
}


def strip_json_comments(value: str) -> str:
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    while index < len(value):
        char = value[index]
        next_char = value[index + 1] if index + 1 < len(value) else ""
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and next_char == "/":
            index += 2
            while index < len(value) and value[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < len(value) and value[index : index + 2] != "*/":
                if value[index] in "\r\n":
                    output.append(value[index])
                index += 1
            index += 2
            continue
        output.append(char)
        index += 1
    without_comments = "".join(output)
    return re.sub(r",\s*([}\]])", r"\1", without_comments)


def load_jsonish(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8-sig")
        value = json.loads(strip_json_comments(raw))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "root is not an object"
    return value, None


def walk_files(repo: Path, max_files: int) -> tuple[list[Path], bool]:
    files: list[Path] = []
    truncated = False
    for root, dirs, names in os.walk(repo):
        dirs[:] = sorted(directory for directory in dirs if directory not in IGNORED_DIRS)
        for name in sorted(names):
            candidate = Path(root) / name
            if not is_within(candidate, repo):
                continue
            files.append(candidate)
            if len(files) >= max_files:
                truncated = True
                return files, truncated
    return files, truncated


def relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def dependency_map(package: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = package.get(key, {})
        if isinstance(values, dict):
            for name, version in values.items():
                if isinstance(name, str) and isinstance(version, str):
                    result[name] = version
    return result


def line_matches(path: Path, patterns: dict[str, re.Pattern[str]]) -> Iterable[dict[str, Any]]:
    try:
        if path.stat().st_size > 1_000_000:
            return []
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return []
    matches: list[dict[str, Any]] = []
    for line_number, content in enumerate(lines, 1):
        for signal, pattern in patterns.items():
            if pattern.search(content):
                matches.append(
                    {
                        "signal": signal,
                        "line": line_number,
                        "snippet": content.strip()[:240],
                    }
                )
    return matches


def infer_package_manager(root_package: dict[str, Any] | None, lockfiles: list[str]) -> str | None:
    if root_package and isinstance(root_package.get("packageManager"), str):
        return root_package["packageManager"]
    mapping = {
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "package-lock.json": "npm",
        "npm-shrinkwrap.json": "npm",
        "bun.lock": "bun",
        "bun.lockb": "bun",
    }
    detected = [mapping[name] for name in lockfiles if name in mapping]
    return detected[0] if len(set(detected)) == 1 else ("multiple" if detected else None)


def build_inventory(repo: Path, max_files: int) -> dict[str, Any]:
    files, truncated = walk_files(repo, max_files)
    rel_files = {relative(repo, path): path for path in files}
    root_package, root_package_error = (
        load_jsonish(repo / "package.json") if (repo / "package.json").is_file() else (None, None)
    )
    package_paths = sorted(name for name in rel_files if name.endswith("package.json"))[:100]
    lock_names = [
        name
        for name in ("pnpm-lock.yaml", "yarn.lock", "package-lock.json", "npm-shrinkwrap.json", "bun.lock", "bun.lockb")
        if name in rel_files
    ]
    dependencies = dependency_map(root_package or {})
    scripts = root_package.get("scripts", {}) if isinstance(root_package, dict) else {}
    if not isinstance(scripts, dict):
        scripts = {}

    frameworks = sorted({label for package, label in FRAMEWORK_PACKAGES.items() if package in dependencies})
    tools = sorted({label for package, label in TOOL_PACKAGES.items() if package in dependencies})
    configs = sorted(
        name
        for name in rel_files
        if Path(name).name
        in {
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "next.config.js",
            "next.config.mjs",
            "next.config.ts",
            "nuxt.config.ts",
            "angular.json",
            "eslint.config.js",
            "eslint.config.mjs",
            ".eslintrc",
            ".prettierrc",
            "turbo.json",
            "nx.json",
            "playwright.config.ts",
            "cypress.config.ts",
        }
    )
    ci_files = sorted(name for name in rel_files if name.startswith(".github/workflows/") or name in {".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile"})

    extension_counts = Counter(path.suffix.lower() or "[no-extension]" for path in files)
    source_files = [path for path in files if path.suffix.lower() in SOURCE_EXTENSIONS]
    risk_matches: list[dict[str, Any]] = []
    for path in source_files:
        for match in line_matches(path, RISK_PATTERNS):
            risk_matches.append({"file": relative(repo, path), **match})
            if len(risk_matches) >= 50:
                break
        if len(risk_matches) >= 50:
            break

    observations: list[dict[str, Any]] = []
    if (repo / "package.json").is_file() and not lock_names:
        observations.append({"id": "lockfile_missing", "summary": "package.json exists but no root lockfile was found"})
    if root_package_error:
        observations.append({"id": "package_json_unreadable", "summary": root_package_error})
    floating = sorted(name for name, version in dependencies.items() if version.strip() in {"latest", "*"})
    if floating:
        observations.append({"id": "floating_dependencies", "summary": "dependencies use floating versions", "packages": floating})
    missing_scripts = [name for name in ("build", "test", "typecheck", "lint") if name not in scripts]
    if missing_scripts:
        observations.append({"id": "quality_scripts_missing", "summary": "common quality scripts were not declared", "scripts": missing_scripts})
    if not ci_files:
        observations.append({"id": "ci_not_detected", "summary": "no supported CI configuration was detected"})

    ts_files_exist = any(path.suffix.lower() in {".ts", ".tsx"} for path in files)
    tsconfig = repo / "tsconfig.json"
    if ts_files_exist:
        if not tsconfig.is_file():
            observations.append({"id": "tsconfig_missing", "summary": "TypeScript source exists but root tsconfig.json was not found"})
        else:
            ts_value, ts_error = load_jsonish(tsconfig)
            if ts_error:
                observations.append({"id": "tsconfig_unreadable", "summary": ts_error})
            else:
                compiler = ts_value.get("compilerOptions", {}) if ts_value else {}
                if not isinstance(compiler, dict) or compiler.get("strict") is not True:
                    observations.append({"id": "typescript_strict_not_enabled", "summary": "compilerOptions.strict is not explicitly true"})

    library_groups: dict[str, list[str]] = {}
    for group, candidates in LIBRARY_GROUPS.items():
        present = sorted(candidates & dependencies.keys())
        if present:
            library_groups[group] = present
        if len(present) > 1:
            observations.append({"id": f"multiple_{group}_libraries", "summary": f"multiple {group} libraries are declared", "packages": present})

    return {
        "schema_version": "inventory-1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo),
        "coverage": {"files_seen": len(files), "max_files": max_files, "truncated": truncated, "ignored_directories": sorted(IGNORED_DIRS)},
        "project": {
            "name": root_package.get("name") if root_package else None,
            "private": root_package.get("private") if root_package else None,
            "package_manager": infer_package_manager(root_package, lock_names),
            "lockfiles": lock_names,
            "package_manifests": package_paths,
            "frameworks": frameworks,
            "tools": tools,
            "scripts": {key: scripts[key] for key in sorted(scripts) if isinstance(scripts[key], str)},
            "library_groups": library_groups,
        },
        "configs": configs,
        "ci": ci_files,
        "stats": {
            "source_file_count": len(source_files),
            "extensions": dict(sorted(extension_counts.items())),
        },
        "signals": risk_matches,
        "observations": observations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path, help="Repository root")
    parser.add_argument("--output", type=Path, help="Write inventory JSON to this path")
    parser.add_argument("--max-files", type=int, default=20000, help="Stop after this many files")
    args = parser.parse_args()
    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"error: repository does not exist: {repo}", file=sys.stderr)
        return 2
    if args.max_files < 1:
        print("error: --max-files must be positive", file=sys.stderr)
        return 2
    inventory = build_inventory(repo, args.max_files)
    if args.output:
        save_json(args.output, inventory)
    else:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
