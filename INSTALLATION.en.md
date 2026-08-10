# Cross-Platform Installation Guide

`frontend-system-review` follows the [Agent Skills open standard](https://agentskills.io/specification) (published by Anthropic in 2025-10, opened as a standard on 2025-12-18). Its `SKILL.md` uses the standard `name`/`description` frontmatter, so it is directly recognized by Codex, Claude Code, OpenCode, Gemini CLI, Cline, Cursor, Copilot, Windsurf, Zed, and more — **only the install directory differs per platform; the format requires zero changes**.

- Chinese site: https://linkingoscar.github.io/frontend-system-review/
- 中文版本文档:见 [INSTALLATION.md](./INSTALLATION.md)

---

## Quick Install

### Option 1: Hand the repo to your AI (easiest)

Paste the repo link into the AI tool you are using and let it install or work directly:

- In a coding agent session that supports skills (Codex, Claude Code, OpenCode, etc.), simply say: **"install the skill at https://github.com/linkingoscar/frontend-system-review"** — the AI clones it into the right directory for your platform.
- Or paste the contents of [SKILL.md](./skills/frontend-system-review/SKILL.md) into the conversation — the AI follows its review disciplines and workflow directly. Works with any conversational AI (ChatGPT, Claude, Gemini, etc.), no local install needed.

### Option 2: skills CLI (recommended)

The [skills CLI](https://www.skills.sh/docs/cli) preserves a common source record and update flow:

```bash
npx skills add linkingoscar/frontend-system-review --skill '*' -g -y
npx skills list -g
npx skills update -g -y
```

Omit `-g` for project scope. For the orchestrator only, replace `--skill '*'` with `--skill frontend-system-review`. The CLI discovers one orchestrator and six specialist skills from the canonical repository directory.

### Option 3: Repository installers

```bash
# macOS / Linux
./install.sh                          # install all 7 skills to ~/.agents/skills by default
./install.sh --platform all           # explicitly install to all platform directories
./install.sh --skill frontend-system-review   # orchestrator only
./install.sh --platform claude,opencode   # only specific platforms
./install.sh --dry-run                # preview what would be done
./install.sh --scope project --project-dir /path/to/project   # project scope
```

```powershell
# Windows (PowerShell 5.1+, pwsh 7 recommended)
powershell -ExecutionPolicy Bypass -File .\install.ps1
.\install.ps1 -Platform generic,claude,opencode
.\install.ps1 -DryRun
.\install.ps1 -Scope project -ProjectDir D:\my-project
```

Script arguments:

| Argument | Description |
|---|---|
| `--platform <list>` / `-Platform` | Comma-separated platforms: `generic,codex,claude,opencode,gemini,cline,cursor,copilot,all` (default: `generic`) |
| `--skill <list>` / `-Skill` | Comma-separated skill names or `all` (default: the complete suite) |
| `--scope user\|project` / `-Scope` | `user`: current user's directories (default); `project`: project directories |
| `--project-dir <dir>` / `-ProjectDir` | Project directory for `--scope project` (default: current dir) |
| `--dry-run` / `-DryRun` | Show what would be done without copying |
| `--force` / `-Force` | Remove existing target before installing |
| `--link` (install.sh only) | Symlink instead of copy (default: copy) |
| `--help` / `-Help` | Show help |

> Both installers copy only canonical skills below `skills/` and verify each copy afterward; release verification ensures that set matches the manifest. Unix can use `--link` for live synchronization.

### Option 4: Clone, then install

```bash
git clone https://github.com/linkingoscar/frontend-system-review.git
cd frontend-system-review
./install.sh --platform generic --skill all

# Pin a reproducible release
git checkout v2.0.1
./install.sh --platform generic --skill all --force
```

> Do not clone the repository root directly into a skill directory. The root is the release/documentation project; installable content lives only in `skills/frontend-system-review/`.

### Option 5: Native commands

```bash
# Gemini CLI
gemini skills install linkingoscar/frontend-system-review --scope user

# skills CLI also supports per-agent distribution
npx skills add linkingoscar/frontend-system-review --skill '*' -a codex -g -y
```

### Option 6: Symlink hub (install once, visible everywhere)

Use `~/.agents/skills` as the single real directory (natively read by Codex, Gemini, Cursor, Copilot, Zed, Windsurf, OpenCode) and symlink the rest:

```bash
ln -s ~/.agents/skills ~/.claude/skills
ln -s ~/.agents/skills ~/.codex/skills
ln -s ~/.agents/skills ~/.gemini/skills
ln -s ~/.agents/skills ~/.cursor/skills
ln -s ~/.agents/skills ~/.copilot/skills
```

> If a target directory already has content, back it up and merge before replacing with a link.

---

## Per-Platform Details

### Codex (OpenAI Codex CLI)

| Scope | Path |
|---|---|
| User | `~/.agents/skills/frontend-system-review/` (current official path) |
| Project | `.agents/skills/frontend-system-review/` (scanned upward from CWD to git root) |
| Community-common (not in official docs) | `~/.codex/skills/frontend-system-review/` |

- **Invocation**: mention `$frontend-system-review`, the `/skills` command, or automatic matching by `description`; `@skill` in ChatGPT.
- **Verify**: type `/skills` in a session — `frontend-system-review` should be listed.
- **Notes**:
  - This repo's `agents/openai.yaml` is **skill-level product metadata** (ChatGPT desktop UI: display_name, short_description, default_prompt, etc.) read by the harness. It is **not** a Codex agent definition — leave it in place; this is exactly the standard Codex skill repo layout.
  - Codex custom subagents are TOML files (`~/.codex/agents/*.toml`, fields `name`/`description`/`developer_instructions`), unrelated to this skill.
  - Codex AGENTS.md is plain-text concatenation; there is no official `@agent` reference syntax (`@path` is a community-requested extension, merge status unconfirmed).
  - Restart Codex after editing SKILL.md; symlinked skills are followed.
  - Skill list budget: max 2% of context or 8000 chars; too many skills truncate descriptions.

### Claude Code

| Scope | Path |
|---|---|
| User | `~/.claude/skills/frontend-system-review/` |
| Project | `.claude/skills/frontend-system-review/` |
| Plugin | `<plugin>/skills/<name>/SKILL.md` (via marketplace) |

- **Invocation**: automatic (model decides by description) or manual `/frontend-system-review`.
- **Verify**: `/skills` in session (skill manager), or trigger `/frontend-system-review`.
- **Notes**:
  - The directory name is the command name; the frontmatter `name` must match the directory name (`frontend-system-review` already complies: lowercase + digits + hyphens).
  - Reference support files with relative paths in SKILL.md (e.g. `references/checklist.md`).
  - Legacy `.claude/commands/*.md` still works, but the skills directory is the modern way.
  - Same-name priority: Enterprise > Personal > Project > built-in.

### OpenCode

| Scope | Path |
|---|---|
| Global | `~/.config/opencode/skills/frontend-system-review/` |
| Project | `.opencode/skills/frontend-system-review/` (from CWD up to git root) |
| Compatible dirs | `~/.claude/skills/`, `~/.agents/skills/` (global); `.claude/skills/`, `.agents/skills/` (project) |

- **Invocation**: loaded by ID via the `skill` tool; `/frontend-system-review` slash command in V2 CLI.
- **Verify**: check the skill list in the `skill` tool description.
- **Notes**: frontmatter recognizes only `name`, `description`, `license`, `compatibility`, `metadata` (all compatible); `name` must match the directory name. Troubleshooting: ALL-CAPS SKILL.md, missing name/description, permission denied, restart.

### Gemini CLI

| Scope | Path |
|---|---|
| User | `~/.gemini/skills/frontend-system-review/` (alias `~/.agents/skills/`) |
| Workspace | `.gemini/skills/frontend-system-review/` (alias `.agents/skills/`) |

- **Install command**: `gemini skills install linkingoscar/frontend-system-review --scope user`
- **Verify**: `gemini skills list --all` or `/skills list` in session.
- **Notes**:
  - The skill name comes from the frontmatter `name` field (not the directory name).
  - Only one level of subdirectory is discovered (`skills/<name>/SKILL.md`); deeper nesting is ignored. Filename must be exactly `SKILL.md` (case-sensitive).
  - Workspace skills require the directory to be trusted (`/trust`); automatic invocation asks for user approval before injecting.

### Cline

| Scope | Path |
|---|---|
| Project (recommended) | `.cline/skills/frontend-system-review/` |
| Alternatives | `.clinerules/skills/`, `.claude/skills/` |
| Global | `~/.cline/skills/` (Windows: `C:\Users\<username>\.cline\skills\`) |

- **Enable**: Settings → Features → Enable Skills (experimental).
- **Invocation**: automatic (`use_skill` tool matches description) or `/frontend-system-review`.
- **Verify**: type `/` to list skill commands, or the Skills tab in the panel.
- **Notes**: global wins over project on same-name conflict (opposite of Claude Code); `.clinerules/` files are always-loaded rules, not on-demand skills.

### Cursor

| Scope | Path |
|---|---|
| Project | `.cursor/skills/frontend-system-review/`, `.agents/skills/` |
| Global | `~/.cursor/skills/`, `~/.agents/skills/` |
| Compatible read | `.claude/skills/`, `.codex/skills/` (project & user) |

- **Invocation**: automatic match or `/frontend-system-review`; categorized subdirectories supported (e.g. `.cursor/skills/review/frontend-system-review/SKILL.md`).
- **Verify**: Settings (Ctrl+Shift+J) → Rules → "Agent Decides" list.

### GitHub Copilot (VS Code / Visual Studio)

| Scope | Path |
|---|---|
| Project | `.github/skills/frontend-system-review/`, `.claude/skills/`, `.agents/skills/` |
| Personal | `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` |

- **Surfaces**: Copilot coding agent, Copilot CLI, cloud agents, VS Code agent mode.
- **Invocation**: `/frontend-system-review` slash command or automatic.
- **Verify**: Chat view gear → Agent Customizations → Skills tab.
- **Notes**: invalid characters in frontmatter `name` fail silently (this skill's name is compliant).

### Windsurf / Zed (summary)

| Platform | User | Project | Activation |
|---|---|---|---|
| Windsurf | `~/.codeium/windsurf/skills/` | `.windsurf/skills/` | `@frontend-system-review` (manual is more reliable) |
| Zed | `~/.agents/skills/` | `.agents/skills/` | automatic (`skill` tool) / `/frontend-system-review` / `@frontend-system-review` |

- Zed supports flat layout only (no `group/name/` nesting); SKILL.md changes hot-reload; project skills require a trusted worktree.
- Windsurf cross-agent compatibility: `.agents/skills/`, `~/.agents/skills/`.

---

## User vs Project Scope

- **User scope**: install once, available in all projects. Good for personal workflows.
- **Project scope**: checked into the repo (e.g. `.agents/skills/` or `.claude/skills/`) for team sharing via git.
- Most platforms support both; priority and same-name override rules differ — see the per-platform notes above.

## Verification Checklist

1. After installing, open a session in the target tool and type `/skills` (Codex/Claude Code/Gemini) or the relevant UI panel; confirm `frontend-system-review` appears with the correct description.
2. Trigger a review (e.g. `use frontend-system-review to review my project`) and confirm SKILL.md gets loaded.
3. Check support files are present: `references/checklist.md`, `scripts/inventory_repo.py`, etc.
4. If the skill does not show up: confirm directory name = `frontend-system-review`, SKILL.md starts with `---` frontmatter, the platform's experimental switch is enabled, and the session was restarted.

## Uninstall

```bash
# Remove per-platform directories (example: Claude Code)
rm -rf ~/.claude/skills/frontend-system-review
# Windows
Remove-Item -Recurse -Force "$env:USERPROFILE\.claude\skills\frontend-system-review"
```

## References

- Agent Skills open standard: https://agentskills.io/specification
- Codex skills docs: https://developers.openai.com/codex/skills
- Claude Code skills docs: https://code.claude.com/docs/en/skills
- OpenCode skills docs: https://opencode.ai/docs/skills/
- Gemini CLI skills docs: https://geminicli.com/docs/cli/skills/
- Cline skills docs: https://docs.cline.bot/customization/skills
- Cursor skills docs: https://cursor.com/docs/skills
- VS Code Agent Skills: https://code.visualstudio.com/docs/agent-customization/agent-skills
- Zed skills docs: https://zed.dev/docs/ai/skills
