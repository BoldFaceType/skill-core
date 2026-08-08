# Changelog entry — append to CHANGELOG.md

## [0.2.0] - 2026-08-08

### Added
- `scripts/lock_sources.py` — generates `sources.lock.json` from `selection.json` via git protocol (no API rate limit). Records commit SHA, blob SHA, sha256, size, and license per skill. Idempotent; `--check` detects upstream drift and exits non-zero for CI.
- `scripts/vendor_skills.py` — materializes locked skills into `skill-core/vendor/`, copies sibling files and the governing LICENSE, and re-verifies each sha256 from disk after writing. Refuses to run against a lock with gaps or rejections.
- `scripts/validate_workflows.py` — verifies stage ordering, durable outputs, skill-reference resolution against the lock, and that no workflow writes into `skill-core/`.
- `skill-core/sources.lock.json` — **23 / 23 skills locked**, status `locked`.
- `skill-core/vendor/**` — 23 skills, 91 files, all hash-verified.
- `workflows/process-discovery/` — manifest, README, and 15 classification eval cases.
- `docs/GLOSSARY.md`, `docs/WHY_FILESYSTEM_AS_STATE.md`, `docs/DOD_POLICY.md`.
- `decisions/0002-process-discovery-as-workflow.md`, `decisions/0003-skillstore-v1x-archived.md`.
- `skill-core/GAP_REPORT_v2.md` (open items) and `GAP_REPORT_v3_RESOLVED.md` (decisions applied).

### Changed
- License verification resolves **per skill**, nearest-first from the skill's own directory upward, rather than per repository.
- Source resolution uses the git protocol rather than the GitHub REST API.
- `selection.json` entries accept an optional `path` field pinning an exact upstream file; lock entries record `path_pinned`.

### Removed from selection
- `xlsx` (anthropics/skills) — all-rights-reserved license, no redistribution grant. Replaced by `gws-sheets` (googleworkspace/cli, Apache-2.0).
- `doc-coauthoring` (anthropics/skills) — no license beside the skill and no repository-root LICENSE. Replaced by `documentation` (anthropics/knowledge-work-plugins, Apache-2.0).

### Renamed in selection
- `to-prd` → `to-spec`; `to-issues` → `to-tickets` (upstream names).

### Added to selection
- `to-questionnaire` (mattpocock/skills) — required by `process-discovery` stage 4.
- `skillopt-sleep` pinned to the Codex platform variant.

### Notes
- Core size is now **23**. PRD FR1's fixed count of 22 should be restated as a property rather than a quantity.
- Nothing was deleted or overwritten in the source material; the prior `selection.json` is preserved via `supersedes` and `amendments_applied`.

### Added (second pass, same date)
- `scripts/verify_core.py` — the FR1 gate. Offline; asserts every core skill is selected, locked, licensed, and vendored, and re-hashes each vendored file against the lock. Negative-tested: tampering and license downgrade each exit 1.
- `docs/PRD.md` v0.2.0 — FR1 restated as a property; FR13 (drift detection) added; "not a runtime" made an explicit non-goal.
- `decisions/0004-fr1-property-not-count.md`.
- `.github/workflows/verify.yml` — CI running all four gates, plus a weekly upstream drift check.
- `INSTALL.md` — install for `C:\Dev\projects\Skill Core`, including a flag on the space in the repository path.

### Changed (second pass)
- **PRD FR1** no longer states a fixed count of 22. It states the property every core skill must satisfy. Core size is an outcome of curation.
