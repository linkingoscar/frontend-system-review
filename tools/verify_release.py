#!/usr/bin/env python3
"""Verify suite release metadata and optional installed-skill parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "release" / "manifest.json"
IGNORED_PARTS = {"__pycache__", ".DS_Store"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_ignored(relative: Path) -> bool:
    return any(part in IGNORED_PARTS for part in relative.parts) or relative.suffix == ".pyc"


def file_map(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if is_ignored(relative):
            continue
        result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def markdown_link_errors(skill: Path) -> list[str]:
    errors: list[str] = []
    sources = [skill / "SKILL.md", *sorted((skill / "references").glob("*.md"))]
    for source in sources:
        text = source.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (source.parent / relative).resolve().exists():
                errors.append(f"broken link in {source.relative_to(skill)}: {target}")
    return errors


def compare_maps(source: dict[str, str], installed: Path) -> dict[str, Any]:
    if not installed.is_dir():
        return {"path": str(installed), "missing_directory": True, "missing": [], "extra": [], "changed": []}
    target = file_map(installed)
    return {
        "path": str(installed),
        "missing_directory": False,
        "missing": sorted(set(source) - set(target)),
        "extra": sorted(set(target) - set(source)),
        "changed": sorted(path for path in set(source) & set(target) if source[path] != target[path]),
    }


def parity_failed(parity: dict[str, Any]) -> bool:
    return bool(parity["missing_directory"] or parity["missing"] or parity["extra"] or parity["changed"])


def validate(installed: Path | None, installed_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_json(MANIFEST_PATH)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "frontend-system-review-release-2.0":
            raise ValueError("unsupported release manifest")
        specs = manifest.get("skills")
        if not isinstance(specs, list) or not specs:
            raise ValueError("release manifest skills must be a non-empty array")
        names = [str(spec.get("name", "")) for spec in specs]
        if len(names) != len(set(names)) or any(not name for name in names):
            raise ValueError("release manifest skill names must be non-empty and unique")
        discovered = sorted(path.name for path in (REPO_ROOT / "skills").iterdir() if path.is_dir() and (path / "SKILL.md").is_file())
        if discovered != sorted(names):
            errors.append(f"skills directory differs from release manifest: discovered={discovered}, declared={sorted(names)}")
        primary_name = str(manifest["primary_skill"])
        if primary_name not in names:
            raise ValueError("primary_skill is not present in skills")

        version_path = (REPO_ROOT / str(manifest["version_file"])).resolve()
        version = version_path.read_text(encoding="utf-8").strip()
        if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
            errors.append(f"invalid VERSION: {version!r}")
        if manifest.get("version") != version:
            errors.append("release manifest version does not match VERSION")
        package = load_json(REPO_ROOT / "package.json")
        if package.get("version") != version:
            errors.append("package.json version does not match VERSION")
        package_lock = load_json(REPO_ROOT / "package-lock.json")
        lock_root = package_lock.get("packages", {}).get("", {}) if isinstance(package_lock, dict) else {}
        if package_lock.get("version") != version or lock_root.get("version") != version:
            errors.append("package-lock.json version does not match VERSION")
        baseline = load_json(REPO_ROOT / str(manifest["standards_baseline"]))
        if baseline.get("skill_version") != version:
            errors.append("standards baseline skill_version does not match VERSION")
        license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
        if "MIT License" not in license_text or "Permission is hereby granted" not in license_text:
            errors.append("LICENSE is not a recognizable MIT license")

        skills: list[dict[str, Any]] = []
        source_maps: dict[str, dict[str, str]] = {}
        for spec in specs:
            name = str(spec["name"])
            skill = (REPO_ROOT / str(spec["directory"])).resolve()
            if not skill.is_dir() or REPO_ROOT not in skill.parents:
                errors.append(f"invalid skill directory for {name}: {skill}")
                continue
            actual_entries = sorted(path.name for path in skill.iterdir() if not is_ignored(Path(path.name)))
            allowed_entries = sorted(str(item) for item in spec.get("allowed_entries", []))
            if actual_entries != allowed_entries:
                errors.append(f"{name} root entries differ from release manifest: actual={actual_entries}, allowed={allowed_entries}")
            for forbidden in ("README.md", "README.en.md", "INSTALLATION.md", "docs", ".git"):
                if (skill / forbidden).exists():
                    errors.append(f"repository-only content leaked into {name}: {forbidden}")
            skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
            header = re.match(r"\A---\s*\n(.*?)\n---", skill_text, re.DOTALL)
            if not header:
                errors.append(f"{name}/SKILL.md has no YAML frontmatter")
            else:
                if not re.search(rf"(?m)^name:\s*{re.escape(name)}\s*$", header.group(1)):
                    errors.append(f"{name}/SKILL.md name is missing or incorrect")
                if not re.search(r"(?m)^description:\s*\S", header.group(1)):
                    errors.append(f"{name}/SKILL.md description is missing")
                if not re.search(r"(?m)^license:\s*MIT\s*$", header.group(1)):
                    errors.append(f"{name}/SKILL.md license must be MIT")
            errors.extend(f"{name}: {item}" for item in markdown_link_errors(skill))
            for json_path in skill.rglob("*.json"):
                load_json(json_path)
            files = file_map(skill)
            if not files:
                errors.append(f"{name} has no files")
            source_maps[name] = files
            skills.append({"name": name, "directory": str(skill), "files": len(files)})

        parity: list[dict[str, Any]] = []
        if installed is not None:
            primary_source = source_maps.get(primary_name, {})
            item = {"name": primary_name, **compare_maps(primary_source, installed.resolve())}
            parity.append(item)
            if parity_failed(item):
                errors.append("installed primary skill differs from its canonical directory")
        if installed_root is not None:
            root = installed_root.resolve()
            for name in names:
                item = {"name": name, **compare_maps(source_maps.get(name, {}), root / name)}
                parity.append(item)
                if parity_failed(item):
                    errors.append(f"installed skill differs from canonical source: {name}")

        return {
            "valid": not errors,
            "version": version,
            "primary_skill": primary_name,
            "skills": skills,
            "files": sum(item["files"] for item in skills),
            "installed_parity": parity or None,
            "errors": errors,
            "warnings": warnings,
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [str(exc)], "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, help="Compare an installed primary skill directory byte-for-byte")
    parser.add_argument("--installed-root", type=Path, help="Compare every suite skill below an installed skills root")
    args = parser.parse_args()
    if args.installed and args.installed_root:
        parser.error("use only one of --installed or --installed-root")
    result = validate(args.installed, args.installed_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
