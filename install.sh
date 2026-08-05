#!/usr/bin/env bash
#
# install.sh — Install the frontend-system-review skill into AI agent skill directories.
#
# Usage:
#   ./install.sh [--platform generic,codex,claude,...] [--scope user|project]
#                [--project-dir <dir>] [--dry-run] [--force] [--link] [--help]
#
# Default: install to all supported platforms' user directories (copy mode).
# Exit code: 0 success (with possible skips), 1 on failure, 2 on bad usage.

set -u

SKILL_NAME="frontend-system-review"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$SCRIPT_DIR"

DRY_RUN=0
FORCE=0
USE_LINK=0
SCOPE="user"
PROJECT_DIR=""
ALL_PLATFORMS="generic,codex,claude,opencode,gemini,cline,cursor,copilot"
PLATFORMS="$ALL_PLATFORMS"

usage() {
    cat <<EOF
Usage: $0 [options]

Install the "$SKILL_NAME" skill into AI agent skill directories.

Options:
  --platform <list>   Comma-separated platforms to install to.
                      Values: generic,codex,claude,opencode,gemini,cline,cursor,copilot
                      (default: all)
  --scope <user|project>
                      user: install into the current user's skill directories (default)
                      project: install into project-level skill directories
  --project-dir <dir> Project directory used with --scope project (default: current dir)
  --dry-run           Show what would be done without copying anything
  --force             Replace existing installation directories
  --link              Symlink the skill directory instead of copying (default: copy)
  --help, -h          Show this help and exit

Verification: run "/skills" inside the target tool's session.
EOF
}

user_platform_dir() {
    case "$1" in
        generic)  echo "$HOME/.agents/skills" ;;
        codex)    echo "$HOME/.codex/skills" ;;
        claude)   echo "$HOME/.claude/skills" ;;
        opencode) echo "$HOME/.config/opencode/skills" ;;
        gemini)   echo "$HOME/.gemini/skills" ;;
        cline)    echo "$HOME/.cline/skills" ;;
        cursor)   echo "$HOME/.cursor/skills" ;;
        copilot)  echo "$HOME/.copilot/skills" ;;
    esac
}

project_platform_dir() {
    local base="$PWD"
    [ -n "$PROJECT_DIR" ] && base="$PROJECT_DIR"
    case "$1" in
        generic)  echo "$base/.agents/skills" ;;
        codex)    echo "$base/.codex/skills" ;;
        claude)   echo "$base/.claude/skills" ;;
        opencode) echo "$base/.opencode/skills" ;;
        gemini)   echo "$base/.gemini/skills" ;;
        cline)    echo "$base/.cline/skills" ;;
        cursor)   echo "$base/.cursor/skills" ;;
        copilot)  echo "$base/.copilot/skills" ;;
    esac
}

# --- Parse arguments ---
while [ $# -gt 0 ]; do
    case "$1" in
        --platform)
            [ $# -lt 2 ] && { echo "error: --platform requires a value" >&2; exit 2; }
            PLATFORMS="$2"; shift 2 ;;
        --scope)
            [ $# -lt 2 ] && { echo "error: --scope requires user|project" >&2; exit 2; }
            SCOPE="$2"
            case "$SCOPE" in user|project) ;; *) echo "error: invalid --scope '$SCOPE' (user|project)" >&2; exit 2 ;; esac
            shift 2 ;;
        --project-dir)
            [ $# -lt 2 ] && { echo "error: --project-dir requires a value" >&2; exit 2; }
            PROJECT_DIR="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --force)   FORCE=1; shift ;;
        --link)    USE_LINK=1; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "error: unknown option '$1' (use --help)" >&2; exit 2 ;;
    esac
done

# --- Validate platforms ---
IFS=',' read -r -a PLATFORM_LIST <<< "$PLATFORMS"
VALID=" generic codex claude opencode gemini cline cursor copilot "
for p in "${PLATFORM_LIST[@]}"; do
    case "$VALID" in
        *" $p "*) ;;
        *) echo "error: unknown platform '$p'" >&2; exit 2 ;;
    esac
done

# --- Install ---
ok=0; skip=0; fail=0

for p in "${PLATFORM_LIST[@]}"; do
    if [ "$SCOPE" = "user" ]; then
        base="$(user_platform_dir "$p")"
    else
        base="$(project_platform_dir "$p")"
    fi
    dest="$base/$SKILL_NAME"
    display="${dest//$HOME/~}"

    if [ -e "$dest" ]; then
        if [ "$FORCE" -eq 0 ]; then
            echo "[skip] $p -> $display: already exists (use --force)"
            skip=$((skip+1))
            continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "[dry-run] $p -> $display (would remove existing, then install)"
            ok=$((ok+1))
            continue
        fi
        rm -rf "$dest" || { echo "[fail] $p -> $display: cannot remove existing directory" >&2; fail=$((fail+1)); continue; }
    fi

    if [ "$DRY_RUN" -eq 1 ]; then
        echo "[dry-run] $p -> $display"
        ok=$((ok+1))
        continue
    fi

    mkdir -p "$base" || { echo "[fail] $p -> $display: cannot create $base" >&2; fail=$((fail+1)); continue; }

    if [ "$USE_LINK" -eq 1 ]; then
        if ln -s "$SOURCE_DIR" "$dest" 2>/dev/null; then
            echo "[ok] $p -> $display (symlink)"
            ok=$((ok+1))
        else
            echo "[fail] $p -> $display: symlink failed (try without --link)" >&2
            fail=$((fail+1))
        fi
        continue
    fi

    if command -v rsync >/dev/null 2>&1; then
        rsync -a --exclude '.git' --exclude 'install.sh' --exclude 'install.ps1' "$SOURCE_DIR/" "$dest/" >/dev/null 2>&1
        copied=$?
    else
        cp -R "$SOURCE_DIR" "$dest" >/dev/null 2>&1
        copied=$?
        if [ "$copied" -eq 0 ]; then
            rm -rf "$dest/.git" "$dest/install.sh" "$dest/install.ps1"
        fi
    fi

    if [ "$copied" -eq 0 ]; then
        echo "[ok] $p -> $display"
        ok=$((ok+1))
    else
        echo "[fail] $p -> $display: copy failed" >&2
        fail=$((fail+1))
    fi
done

echo ""
echo "Summary: $ok installed, $skip skipped, $fail failed"
[ "$DRY_RUN" -eq 1 ] && echo "Dry run only - nothing was copied."
if [ "$fail" -gt 0 ]; then
    exit 1
fi
if [ "$DRY_RUN" -eq 0 ] && [ "$ok" -gt 0 ]; then
    echo "Verify: run /skills inside the target tool's session."
fi
exit 0
