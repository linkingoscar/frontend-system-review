# Frontend System Review v2.0.0

This major release turns the project into a verifiable seven-skill review suite and closes the largest runtime evidence gap.

## Highlights

- One orchestrator plus six independently installable specialists: architecture, change, Web runtime, accessibility, visual design, and release.
- Declarative interaction scenarios for login/session, menus, dialogs, form errors, capacity states, round trips, retry, undo, and recovery.
- Step-by-step state films with before/after screenshots, semantic state diffs, screenshot SHA-256, optional PNG diff images, and CI-capable interaction gates.
- A canonical `skills/` source layout, byte-for-byte installer verification, deterministic ZIP/SHA256 assets, MIT license, cross-platform CI, and monthly standards-freshness checks.
- 37 deterministic and real-browser evals.

## Breaking installation change

The repository root is no longer itself an installable skill. Canonical skills now live below `skills/`. This prevents README, website, installer, and release infrastructure from leaking into installed copies.

Install or migrate the complete suite with:

```bash
npx skills add linkingoscar/frontend-system-review --skill '*' -g -y
```

For only the orchestrator, replace `--skill '*'` with `--skill frontend-system-review`.

See [CHANGELOG.md](https://github.com/linkingoscar/frontend-system-review/blob/v2.0.0/CHANGELOG.md) for the full change list.
