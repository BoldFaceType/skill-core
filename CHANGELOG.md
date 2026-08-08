# Changelog

All notable changes to Skill Core are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/);
versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-08

Source lock, license verification, vendoring, and projection. CI green.

### Added

- `scripts/lock_sources.py` — generates `sources.lock.json` from `selection.json`
  over the git protocol (no API rate limit). Records commit SHA, blob SHA,
  sha256, size, and license per skill. Idempotent; `--check` detects upstream
  drift and exits non-zero for CI.
- `scripts/vendor_skills.py` — materializes locked skills into
  `skill-core/vendor/`, copies sibling files and the governing LICENSE, and
  re-verifies each sha256 from disk after writing. Refuses to run against a lock
  with gaps or rejections.
- `scripts/verify_core.py` — the FR1 gate. Offline; asserts every core skill is
  selected, locked, licensed, and vendored.
- `scripts/validate_workflows.py` — stage ordering, durable outputs, skill
  references resolve against the lock, no workflow writes into `skill-core/`.
- `scripts/project_skills.py` — materializes `.agents/skills/`, generates one
  entrypoint skill per workflow, and records ownership in
  `.skillstore-projection.json` so refreshes never touch unmanaged skills.
- `skill-core/sources.lock.json` — 23 / 23 skills, status `locked`.
- `skill-core/vendor/**` — 23 skills, 91 files, all hash-verified.
- `workflows/process-discovery/` — manifest, README, 15 classification cases.
- `docs/PRD.md` v0.2.0, `docs/GLOSSARY.md`, `docs/WHY_FILESYSTEM_AS_STATE.md`,
  `docs/DOD_POLICY.md`.
- `decisions/0002`–`0005`.
- `.github/workflows/verify.yml` — five gates plus a weekly upstream drift check.
- `INSTALL.md`.

### Changed

- **PRD FR1** no longer states a fixed count of 22. It states the property every
  core skill must satisfy — selected, locked, licensed, vendored — and asserts no
  size. Core size is an outcome of curation. (ADR-0004)
- **PRD FR9** no longer requires a packaged CLI. The interface is stdlib-only
  scripts invoked identically by the shell, Marimo, and CI. (ADR-0005)
- License verification resolves **per skill**, nearest-first from the skill's own
  directory upward, rather than per repository.
- Source resolution uses the git protocol rather than the GitHub REST API.
- `selection.json` entries accept an optional `path` pinning an exact upstream
  file; lock entries record `path_pinned`.

### Removed from selection

- `xlsx` (anthropics/skills) — all-rights-reserved license, no redistribution
  grant. Replaced by `gws-sheets` (googleworkspace/cli, Apache-2.0).
- `doc-coauthoring` (anthropics/skills) — no license beside the skill and no
  repository-root LICENSE. Replaced by `documentation`
  (anthropics/knowledge-work-plugins, Apache-2.0).

### Renamed in selection

- `to-prd` → `to-spec`; `to-issues` → `to-tickets` (actual upstream names).

### Added to selection

- `to-questionnaire` (mattpocock/skills) — required by `process-discovery`
  stage 4.
- `skillopt-sleep` pinned to the Codex platform variant.

### Verification

Every claim above has a check behind it that exits non-zero when violated.

| Gate | Result |
|---|---|
| `verify_core.py` | FR1 holds, 23/23 |
| `validate_workflows.py` | 1 workflow, 0 failures, 0 warnings |
| `project_skills.py` | 23 core + 1 entrypoint, 0 failures |
| `lock_sources.py --check` | lock matches upstream |
| `vendor_skills.py --dry-run` | vendoring current |
| GitHub Actions `verify` | ✅ green |

Negative-tested rather than assumed:

- Tampering with a vendored `SKILL.md` → `VENDOR HASH MISMATCH`, exit 1.
- Downgrading a lock entry to a non-permissive license → `NOT LICENSED`, exit 1.
- A hand-installed skill in `.agents/skills/` survives a projection refresh.

### Notes

- Two skills failed license verification and were replaced rather than retained.
  A fixed core size would have created pressure to keep them; see ADR-0004.
- The `skillstore` console script documented in the v0.1.0 README never existed.
  Its absence was treated as a blocker for several milestones before being
  recognized as unnecessary; see ADR-0005.

## [0.1.0] - 2026-08-04

### Added

- Filesystem-as-state boundaries; `skill-core/` as the canonical store.
- 22 selected upstream skill IDs (selected, not locked).
- Declarative workflow schema via TOML manifests.
- Projection engine design and Marimo control-surface skeleton.
- GitHub/Linear ownership ADR; initial tests and repository validation.

### Known gap at 0.1.0

- `sources.lock.json` absent; `core_skills_materialized: 0`.

[0.2.0]: https://github.com/BoldFaceType/skill-core/compare/v0.1.0...v0.2.0
