#!/usr/bin/env python3
"""Build a deterministic skill ZIP and SHA256SUMS for a tagged release."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

from verify_release import MANIFEST_PATH, REPO_ROOT, file_map, validate


TEXT_EXTENSIONS = {".cjs", ".css", ".html", ".js", ".json", ".md", ".ps1", ".py", ".sh", ".txt", ".yaml", ".yml"}


def canonical_payload(source: Path) -> bytes:
    """Return cross-platform stable bytes for release archives."""
    payload = source.read_bytes()
    if source.name == "VERSION" or source.suffix.lower() in TEXT_EXTENSIONS or not source.suffix:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            return payload
        return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = validate(None, None)
    if not verification["valid"]:
        print(json.dumps(verification, ensure_ascii=False, indent=2))
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = manifest["version"]
    prefix = manifest["release_asset_prefix"]
    archive_root = manifest["archive_root"]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"{prefix}-v{version}.zip"
    if archive.exists():
        archive.unlink()

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        license_source = REPO_ROOT / "LICENSE"
        license_info = zipfile.ZipInfo(f"{archive_root}/LICENSE", date_time=(1980, 1, 1, 0, 0, 0))
        license_info.create_system = 3
        license_info.compress_type = zipfile.ZIP_STORED
        license_info.external_attr = 0o644 << 16
        bundle.writestr(license_info, canonical_payload(license_source), compress_type=zipfile.ZIP_STORED)
        for spec in sorted(manifest["skills"], key=lambda item: item["name"]):
            skill = REPO_ROOT / spec["directory"]
            for relative in sorted(file_map(skill)):
                source = skill / relative
                info = zipfile.ZipInfo(f"{archive_root}/{spec['name']}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = (0o755 if source.suffix in {".py", ".cjs"} else 0o644) << 16
                bundle.writestr(info, canonical_payload(source), compress_type=zipfile.ZIP_STORED)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    sums = output / "SHA256SUMS"
    sums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8", newline="\n")
    metadata = output / "release-metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "schema_version": "frontend-system-review-release-asset-2.0",
                "version": version,
                "archive": archive.name,
                "sha256": digest,
                "skills": [spec["name"] for spec in manifest["skills"]],
                "files": verification["files"] + 1,
                "license": "MIT",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"ok": True, "archive": str(archive), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
