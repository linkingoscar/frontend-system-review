# Frontend System Review

> An evidence-driven frontend system review skill — systematic review of repositories, architectures, PRs, and running web interfaces.

Covers business fit, tech stack & dependencies, module boundaries, type & API contracts, state & data flow, rendering & performance, UI/UX & design systems, accessibility, testing, CI/CD, release, security, and observability. It works from the perspective of a senior frontend architect, web quality engineer, and product design reviewer — prioritizing whether a system is **correct, accessible, maintainable, measurable, and safe to ship**; "using a trendy stack" is not treated as proof of maturity.

[中文 README](./README.md) · [GitHub Pages site](https://linkingoscar.github.io/frontend-system-review/)

---

## Features

- **Evidence-driven** — every finding carries `file:line`, tool output, or runtime measurement; facts, inferences, and unknowns are strictly separated; files, line numbers, command results, screenshots, or metrics are never fabricated.
- **Four review modes** — repository system review / change review / runtime experience review / proposal review.
- **Three depths** — quick scan / standard review / deep audit (standard is the default).
- **Strict quality gates** — P0/P1/P2 severity, severity-vs-confidence separation, 12-dimension scoring, evidence coverage, ship-readiness verdicts, with mechanical validation and CI gating.
- **Deterministic toolchain** — 13 scripts (Python stdlib / Node only): inventory, change scope, finding verification, scoring, rendering, baseline diff, gate, SARIF export, one-shot review bundle.
- **Reproducible auditing** — Playwright runtime evidence collection (screenshots, console, network, LCP/CLS, contrast, axe), with 32 eval tests guarding tool behavior.

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

32 tests invoke the scripts through subprocess, covering: repo inventory; evidence validation (out-of-range line numbers, path escape, duplicate fingerprints); P0 gate; scoring & coverage; Markdown rendering stability; command redaction & exit codes; runtime browser collection (desktop + mobile viewports, overflow/contrast/axe); `--fail-on-budget`; baseline gating; SARIF export; bundle build and SHA-256 tamper detection. Runtime-dependent tests run when `FRONTEND_REVIEW_NODE_MODULES` is set, otherwise they skip.

## Cross-Platform Installation

Compatible with the [Agent Skills open standard](https://agentskills.io/specification). Works with Codex, Claude Code, OpenCode, Gemini CLI, Cline, Cursor, Copilot, Windsurf, Zed, and more — only the install directory differs per platform; the format requires zero changes. Full guide: [INSTALLATION.en.md](./INSTALLATION.en.md).

```bash
./install.sh            # macOS / Linux: install to all platforms
# Windows:
powershell -ExecutionPolicy Bypass -File .\install.ps1
# Specific platforms only:
./install.sh --platform claude,opencode
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
3. **Formal delivery**: persist the report as JSON conforming to `scripts/report.schema.json`, then produce the validated review bundle (JSON/Markdown/SARIF/gate/manifest) with `build_review_bundle.py`.

## Directory Structure

```text
frontend-system-review/
├── SKILL.md                     # skill definition (disciplines, modes, workflow)
├── agents/openai.yaml           # skill frontend metadata (Codex/ChatGPT desktop)
├── INSTALLATION.md / .en.md     # cross-platform install guides (CN/EN)
├── install.sh / install.ps1     # one-click install scripts (macOS/Linux / Windows)
├── references/                  # 7 on-demand review reference docs
├── scripts/                     # 13 deterministic tool scripts + 3 schema contracts
├── evals/                       # 32 unittest tests & fixtures
└── docs/                        # GitHub Pages site
```

## License

Not specified. Confirm with the author before use.

---

*Frontend System Review — evidence-driven frontend system review.*
