# Frontend System Review

[![Version](https://img.shields.io/github/v/release/linkingoscar/frontend-system-review?color=orange&label=Version)](https://github.com/linkingoscar/frontend-system-review/releases)
[![CI](https://github.com/linkingoscar/frontend-system-review/actions/workflows/ci.yml/badge.svg)](https://github.com/linkingoscar/frontend-system-review/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Standard-4CAF50)](https://agentskills.io/specification)
[![OpenCode](https://img.shields.io/badge/OpenCode-Compatible-000000)](#)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Compatible-CC0000?logo=anthropic&logoColor=white)](#)
[![Codex](https://img.shields.io/badge/Codex-Compatible-000000?logo=openai&logoColor=white)](#)
[![Gemini CLI](https://img.shields.io/badge/Gemini%20CLI-Compatible-4285F4?logo=google&logoColor=white)](#)
[![Cline](https://img.shields.io/badge/Cline-Compatible-4B32C3)](#)
[![Cursor](https://img.shields.io/badge/Cursor-Compatible-000000)](#)
[![Copilot](https://img.shields.io/badge/Copilot-Compatible-000000?logo=github&logoColor=white)](#)
[![Windsurf](https://img.shields.io/badge/Windsurf-Compatible-00A3FF)](#)
[![Zed](https://img.shields.io/badge/Zed-Compatible-000000)](#)
[![Evidence-Driven](https://img.shields.io/badge/Evidence--Driven-Yes-1E88E5)](#)
[![Bilingual](https://img.shields.io/badge/Bilingual-ZH%2FEN-00897B)](#)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-Live-2EA44F)](https://linkingoscar.github.io/frontend-system-review/)

> An evidence-driven frontend system review skill — systematic review of repositories, architectures, PRs, and running web interfaces.

Covers business fit, tech stack & dependencies, module boundaries, type & API contracts, state & data flow, rendering & performance, UI/UX & design systems, accessibility, testing, CI/CD, release, security, and observability. It works from the perspective of a senior frontend architect, web quality engineer, and product design reviewer — prioritizing whether a system is **correct, accessible, maintainable, measurable, and safe to ship**; "using a trendy stack" is not treated as proof of maturity.

[中文 README](./README.md) · [GitHub Pages site](https://linkingoscar.github.io/frontend-system-review/)

---

## Features

- **Evidence-driven** — every finding carries `file:line`, tool output, or runtime measurement; facts, inferences, and unknowns are strictly separated; files, line numbers, command results, screenshots, or metrics are never fabricated.
- **Four review modes** — repository system review / change review / runtime experience review / proposal review.
- **Three depths** — quick scan / standard review / deep audit (standard is the default).
- **Specialist orchestration** — one orchestrator plus six independently installable architecture, change, runtime, accessibility, visual, and release skills; broad reviews load only the minimum relevant set.
- **Strict quality gates** — P0/P1/P2 severity, severity-vs-confidence separation, 12-dimension scoring, evidence coverage, ship-readiness verdicts, with mechanical validation and CI gating.
- **Deterministic toolchain** — 14 scripts (Python stdlib / Node only): inventory, change scope, finding verification, scoring, rendering, baseline diff, gate, SARIF export, review bundles, and standards-freshness checks.
- **Reproducible auditing** — declarative Playwright flows produce step-by-step state films, screenshot SHA/PNG diffs, console/network/LCP/CLS/contrast/axe evidence; 37 eval tests guard behavior.
- **Verifiable releases** — `VERSION` is the single version source; CI checks source/install/archive parity and enforces a 90-day WCAG/CWV/SARIF snapshot review window.

## Review Modes

| Mode | Suitable Input | Default Output |
|---|---|---|
| Repository System Review | Full project, directory, or stack | Architecture & engineering quality report |
| Change Review | PR, diff, commits, or a few files | Only issues introduced or amplified by the change |
| Runtime Experience Review | URL, local page, screenshot, or runnable app | Responsive, interaction, a11y, performance & visual issues |
| Proposal Review | RFC, architecture diagram, selection notes | Decision risks, alternatives, and a verification plan |

## Core Disciplines

1. Inspect existing materials before asking questions. Don't make users repeat information obtainable from the repo or a running page.
2. Separate facts, inferences, and unknowns. Never write source-code inferences as runtime facts, and never fabricate files, line numbers, command results, screenshots, or metrics.
3. Every issue must include evidence, user/business impact, a concrete fix, and a verification method; unlocatable vague opinions do not enter the findings.
4. Separate severity from confidence. High-impact items lacking evidence are marked "to verify", not judged P0 outright.
5. Report conclusion-changing issues first, polish items later. Don't dilute risks with long lists of strengths.
6. Modify code only when the user asks. Review, diagnostic, and explanation requests are read-only by default.
7. Match business and team constraints. Don't default to recommending micro-frontends, monorepos, large design systems, or rewrites.

## Workflow

```text
Define scope → Build project profile → Risk-first scan → Collect verifiable evidence → Execute relevant dimensions
→ Runtime verification → Parallel investigation & independent verification → Calibrate findings → Score & ship verdict → Deliver
```

- **Risk first**: check things that can block usage, release, or rollback (leaks/XSS, core-flow correctness, build failures, blocking a11y issues, layout breakage, untraceable releases) before polish items.
- **Conflict order**: security & data correctness > core task usability & accessibility > release & recovery capability > performance & layout stability > maintainability & delivery efficiency > visual consistency & polish.
- **Runtime verification**: prefer production builds; check at least desktop and mobile viewports; state-change conclusions must cite two distinguishable before/after artifacts; when runtime is unavailable, explicitly list "statically confirmable / needs runtime verification / not covered this pass".
- **Independent verification**: candidate P0/P1 findings and release gates are reproduced and falsified by a verifier who did not write the finding, preventing confirmation bias.

## Scoring & Verdicts

| Dimension | Description |
|---|---|
| Evidence status | Confirmed / Highly likely / To verify / N/A |
| Severity | P0 blocks release / P1 important / P2 improvement |
| Scoring | 12 dimensions scored 0–5, default weights sum to 100; grade A (85+) B (70+) C (55+) D; evidence coverage <70% marked "provisional" |
| Ship verdict | Blocks release / Ready after fixes / Ship with follow-ups / Acceptable / Unable to determine |

Any confirmed P0 overrides the total score; unchecked dimensions are marked `N/A`, never scored 0 automatically; scores are not disguised as objective measurements — the report states the scoring basis and limits.

## Toolchain

| Script | Purpose |
|---|---|
| `inventory_repo.py` | Deterministic repository inventory (framework/tooling/config/risk signals), emitting observations & signals for human confirmation |
| `collect_change_scope.py` | Collect changed files and line ranges for PR/commit/workspace, with risk categorization |
| `verify_findings.py` | Strict mechanical finding validation (structure, enums, source refs, quote matching, P0 evidence gate), `--strict` |
| `capture_command.py` | Run project commands and persist full redacted stdout/stderr, exit code, hashes, and environment metadata |
| `score_report.py` | Compute total score, grade, and evidence coverage with default 12-dimension weights |
| `render_report.py` | Deterministically render a JSON report into Chinese Markdown |
| `gate_report.py` | CI gate decision; default policy blocks `block`, `ready_after_fixes`, `unable_to_determine` verdicts and confirmed P0 |
| `export_sarif.py` | Export GitHub Code Scanning-compatible SARIF 2.1.0 (confirmed findings with source locations by default) |
| `compare_reports.py` | Diff baseline vs current report by stable fingerprint: new / resolved / changed / regressed / unchanged |
| `build_review_bundle.py` | One-shot review bundle build (validated JSON, Markdown, SARIF, gate result, optional baseline diff, SHA-256 manifest) |
| `verify_review_bundle.py` | Verify bundle manifest hashes, evidence, and gate (tamper detection) |
| `review_common.py` | Shared constants (12-dimension weights, severity/confidence/verdict enums) and JSON utilities |
| `runtime_audit.cjs` | Playwright browser evidence collection (screenshots/DOM/console/network/LCP/CLS/contrast/optional axe); heuristic evidence, never auto-graded |

## References

Paths below are relative to the installed skill root. The canonical repository source is `skills/frontend-system-review/`.

| File | Purpose |
|---|---|
| `references/checklist.md` | Engineering & architecture review checklist (12 sections: business, dependencies & build, architecture & boundaries, types & data, state & rendering, components & design systems, testing, CI/CD, security, observability, scenario addenda, red flags & counter-arguments) |
| `references/web-quality.md` | Web runtime quality (8 dimensions: route/task matrix, a11y, forms & interaction, responsive & layout stability, performance & CWV, SEO, content/i18n/theme, verification protocol) |
| `references/visual-design.md` | Visual & design-system review guide (10 review dimensions, design system details, visual anti-patterns, screenshot & reporting method) |
| `references/evidence-and-scoring.md` | Evidence status, severity, finding quality gates, scoring model, ship-verdict rules |
| `references/report-template.md` | Report templates (formal 10-section / compact / no-findings) |
| `references/tooling.md` | Toolchain usage, output directories, exit-code conventions |
| `references/orchestration.md` | Parallel investigation & independent verification orchestration (roles, context isolation, evidence handoff, merge & stop conditions) |

## Tests

```bash
python -m unittest discover -s evals
```

37 tests invoke the scripts through subprocess, covering inventory, evidence validation, P0 gates, scoring, rendering, command capture, desktop/mobile browser collection, declarative interaction films, PNG diffs, interaction/performance gates, baselines, SARIF, bundles and tamper detection, plus multi-skill release layout, version, and standards-freshness consistency. Runtime-dependent tests run when `FRONTEND_REVIEW_NODE_MODULES` is set, otherwise they skip.

## Cross-Platform Installation

Compatible with the [Agent Skills open standard](https://agentskills.io/specification). Works with Codex, Claude Code, OpenCode, Gemini CLI, Cline, Cursor, Copilot, Windsurf, Zed, and more. See [INSTALLATION.en.md](./INSTALLATION.en.md). All seven canonical skill sources live under [`skills/`](./skills).

```bash
npx skills add linkingoscar/frontend-system-review --skill '*' -g -y
# For the orchestrator only, replace --skill '*' with --skill frontend-system-review
# Update the installed suite:
npx skills update -g -y

./install.sh            # macOS / Linux: install to ~/.agents/skills by default
# Windows:
powershell -ExecutionPolicy Bypass -File .\install.ps1
# Specific platforms or all platforms:
./install.sh --platform claude,opencode
./install.sh --platform all
```

| Platform | User-level directory | Verify in session |
|---|---|---|
| Codex | `~/.agents/skills/` | `/skills` |
| Claude Code | `~/.claude/skills/` | `/skills` |
| OpenCode | `~/.config/opencode/skills/` | `skill` tool list |
| Gemini CLI | `~/.gemini/skills/` | `gemini skills list` |
| Cline | `~/.cline/skills/` | Skills tab |
| Cursor | `~/.cursor/skills/` | Rules → Agent Decides |
| Copilot | `~/.copilot/skills/` | Skills tab |
| Universal (recommended) | `~/.agents/skills/` (natively read by Codex, Gemini, Cursor, Copilot, Zed, Windsurf, OpenCode) | `/skills` |

## Quick Start

1. **Install**: see [Cross-Platform Installation](#cross-platform-installation) and [INSTALLATION.en.md](./INSTALLATION.en.md).
2. **Request a review**: provide a repo path, PR link, live URL, or proposal document; the skill picks the mode and depth automatically.
3. **Formal delivery**: persist the report as JSON conforming to `skills/frontend-system-review/scripts/report.schema.json`, then produce the validated review bundle (JSON/Markdown/SARIF/gate/manifest) with `build_review_bundle.py`.

## Directory Structure

```text
frontend-system-review/
├── skills/                       # 7 canonical, independently discoverable skills
│   ├── frontend-system-review/   # orchestrator, reports, tools, standards snapshot
│   ├── frontend-architecture-review/
│   ├── frontend-change-review/
│   ├── web-runtime-review/
│   ├── accessibility-review/
│   ├── visual-design-review/
│   └── frontend-release-review/
├── INSTALLATION.md / .en.md     # cross-platform install guides (CN/EN)
├── install.sh / install.ps1     # one-click install scripts (macOS/Linux / Windows)
├── tools/                       # release verification and deterministic packaging
├── release/manifest.json        # release boundary and version contract
├── evals/                       # 37 unittest tests & fixtures
├── .github/workflows/           # cross-platform CI and tagged releases
└── docs/                        # GitHub Pages site
```

## License

[MIT](./LICENSE)

---

*Frontend System Review — evidence-driven frontend system review.*
