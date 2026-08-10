# Changelog

All notable changes are documented here. Versions follow Semantic Versioning.

## [2.0.0] - 2026-08-10

### Added

- Six independently discoverable specialist skills for architecture, change, runtime, accessibility, visual design, and release review, coordinated by `frontend-system-review`.
- Declarative runtime scenarios with safe locator/action allowlists, environment-backed sensitive values, state films, screenshot SHA-256, optional PNG diffs, and interaction-failure gating.
- Versioned WCAG/CWV/SARIF standards snapshot with a 90-day freshness check.
- Cross-platform CI, deterministic suite archives, install/source parity verification, and tagged GitHub Releases.

### Changed

- **Breaking:** canonical installable skills now live below `skills/`; the repository root is release and documentation infrastructure, not a skill directory.
- `VERSION` is the single release/tool version source. The suite, package lock, standards snapshot, SARIF, runtime output, and release assets are checked against it.
- Repository installers default to the generic Agent Skills directory and install the complete seven-skill suite; platform fan-out requires an explicit `all`.

### Migration

Use `npx skills add linkingoscar/frontend-system-review --skill '*' -g -y`, or clone the repository outside an agent skill directory and run its installer with `--force` / `-Force`.

## [1.0.0] - 2026-08-05

- Initial public release of the evidence-driven frontend system review skill.

[2.0.0]: https://github.com/linkingoscar/frontend-system-review/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/linkingoscar/frontend-system-review/releases/tag/v1.0.0
