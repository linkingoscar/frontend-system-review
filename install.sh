#!/usr/bin/env bash
# Install the Frontend System Review suite from the canonical skills/ directory.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$SCRIPT_DIR/skills"
DRY_RUN=0
FORCE=0
USE_LINK=0
SCOPE="user"
PROJECT_DIR=""
ALL_PLATFORMS="generic,codex,claude,opencode,gemini,cline,cursor,copilot"
PLATFORMS="generic"
SKILLS="all"

usage() {
  cat <<EOF
Usage: $0 [--platform <list|all>] [--skill <list|all>] [--scope user|project]
          [--project-dir <dir>] [--dry-run] [--force] [--link] [--help]

Defaults: platform=generic, skill=all, scope=user, copy mode.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --platform) [ $# -ge 2 ] || { echo "error: --platform requires a value" >&2; exit 2; }; PLATFORMS="$2"; shift 2 ;;
    --skill) [ $# -ge 2 ] || { echo "error: --skill requires a value" >&2; exit 2; }; SKILLS="$2"; shift 2 ;;
    --scope) [ $# -ge 2 ] || { echo "error: --scope requires a value" >&2; exit 2; }; SCOPE="$2"; shift 2 ;;
    --project-dir) [ $# -ge 2 ] || { echo "error: --project-dir requires a value" >&2; exit 2; }; PROJECT_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --force) FORCE=1; shift ;;
    --link) USE_LINK=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) echo "error: unknown option '$1'" >&2; exit 2 ;;
  esac
done

case "$SCOPE" in user|project) ;; *) echo "error: invalid scope '$SCOPE'" >&2; exit 2 ;; esac
[ "$PLATFORMS" = "all" ] && PLATFORMS="$ALL_PLATFORMS"
IFS=',' read -r -a PLATFORM_LIST <<< "$PLATFORMS"
VALID_PLATFORMS=" generic codex claude opencode gemini cline cursor copilot "
for item in "${PLATFORM_LIST[@]}"; do
  case "$VALID_PLATFORMS" in *" $item "*) ;; *) echo "error: unknown platform '$item'" >&2; exit 2 ;; esac
done

AVAILABLE_SKILLS=""
for directory in "$SOURCE_ROOT"/*; do
  [ -f "$directory/SKILL.md" ] || continue
  name="$(basename "$directory")"
  AVAILABLE_SKILLS="$AVAILABLE_SKILLS $name"
done
[ -n "$AVAILABLE_SKILLS" ] || { echo "error: no canonical skills found below $SOURCE_ROOT" >&2; exit 1; }

if [ "$SKILLS" = "all" ]; then
  SKILL_LIST=($AVAILABLE_SKILLS)
else
  IFS=',' read -r -a SKILL_LIST <<< "$SKILLS"
fi
for item in "${SKILL_LIST[@]}"; do
  case " $AVAILABLE_SKILLS " in *" $item "*) ;; *) echo "error: unknown skill '$item'" >&2; exit 2 ;; esac
done

user_platform_dir() {
  case "$1" in
    generic) echo "$HOME/.agents/skills" ;; codex) echo "$HOME/.codex/skills" ;;
    claude) echo "$HOME/.claude/skills" ;; opencode) echo "$HOME/.config/opencode/skills" ;;
    gemini) echo "$HOME/.gemini/skills" ;; cline) echo "$HOME/.cline/skills" ;;
    cursor) echo "$HOME/.cursor/skills" ;; copilot) echo "$HOME/.copilot/skills" ;;
  esac
}

project_platform_dir() {
  local root="${PROJECT_DIR:-$PWD}"
  case "$1" in
    generic) echo "$root/.agents/skills" ;; codex) echo "$root/.codex/skills" ;;
    claude) echo "$root/.claude/skills" ;; opencode) echo "$root/.opencode/skills" ;;
    gemini) echo "$root/.gemini/skills" ;; cline) echo "$root/.cline/skills" ;;
    cursor) echo "$root/.cursor/skills" ;; copilot) echo "$root/.copilot/skills" ;;
  esac
}

ok=0; skip=0; fail=0
for platform in "${PLATFORM_LIST[@]}"; do
  if [ "$SCOPE" = "user" ]; then base="$(user_platform_dir "$platform")"; else base="$(project_platform_dir "$platform")"; fi
  for skill in "${SKILL_LIST[@]}"; do
    source="$SOURCE_ROOT/$skill"
    dest="$base/$skill"
    display="${dest//$HOME/~}"
    if [ -z "$base" ] || [ "$dest" != "$base/$skill" ] || [ "$dest" = "/" ]; then
      echo "[fail] unsafe target '$dest'" >&2; fail=$((fail+1)); continue
    fi
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      if [ "$FORCE" -eq 0 ]; then echo "[skip] $platform/$skill -> $display (use --force)"; skip=$((skip+1)); continue; fi
      if [ "$DRY_RUN" -eq 0 ]; then rm -rf "$dest" || { echo "[fail] cannot remove $display" >&2; fail=$((fail+1)); continue; }; fi
    fi
    if [ "$DRY_RUN" -eq 1 ]; then echo "[dry-run] $platform/$skill -> $display"; ok=$((ok+1)); continue; fi
    mkdir -p "$base" || { echo "[fail] cannot create $base" >&2; fail=$((fail+1)); continue; }
    if [ "$USE_LINK" -eq 1 ]; then
      if ln -s "$source" "$dest"; then echo "[ok] $platform/$skill -> $display (symlink)"; ok=$((ok+1)); else fail=$((fail+1)); fi
    else
      cp -R "$source" "$dest" >/dev/null 2>&1
      if [ $? -eq 0 ] && diff -qr "$source" "$dest" >/dev/null 2>&1; then
        echo "[ok] $platform/$skill -> $display"; ok=$((ok+1))
      else
        echo "[fail] $platform/$skill copy or verification failed" >&2; fail=$((fail+1))
      fi
    fi
  done
done

echo ""
echo "Summary: $ok installed, $skip skipped, $fail failed"
[ "$DRY_RUN" -eq 1 ] && echo "Dry run only - nothing was copied."
[ "$fail" -gt 0 ] && exit 1
exit 0
