# Skill Core — VSA 0.2 Bundle

**Date:** 2026-08-08 · **Milestone:** VSA 0.2 (source lock) + VSA 0.5 groundwork
**Status:** PASS — 23/23 locked, licensed, and vendored

Additive bundle for the Skill Core repository (formerly titled "SkillStore v3"). **Nothing here deletes or overwrites existing files.** The original `selection.json` (2026-08-04) is preserved via `supersedes` + `amendments_applied` inside the amended file; the superseded gap reports are retained rather than removed.

## What's here

```
scripts/
  verify_core.py               FR1 gate: selected + locked + licensed + vendored (offline)
  lock_sources.py              generates sources.lock.json; --check for CI drift detection
  vendor_skills.py             materializes + hash-verifies skill-core/vendor/
  validate_workflows.py        verifies stage skill refs resolve against the lock
skill-core/
  selection.json               amended: 23 skills, supersedes the 2026-08-04 list
  sources.lock.json            23 skills locked with commit + blob SHA + sha256 + license
  vendor/                      23 vendored skills, 91 files, hash-verified
  GAP_REPORT_v3_RESOLVED.md    decisions applied, final state
  GAP_REPORT_v2.md             the open items (retained)
  GAP_REPORT.md                superseded first pass (retained)
  gap_report.json              now empty — no gaps, no rejections
  selection.proposed.json      the proposal that was accepted (retained)
docs/
  PRD.md                       v0.2.0 — FR1 restated as a property
  GLOSSARY.md                  Skill Core vs SkillStore v1.x vs PDE vs Filesystem-As-State
  WHY_FILESYSTEM_AS_STATE.md   design rationale, relocated from standalone canvas
  DOD_POLICY.md                no [x] without a verifying test
decisions/
  0002-process-discovery-as-workflow.md
  0003-skillstore-v1x-archived.md
  0004-fr1-property-not-count.md
.github/workflows/
  verify.yml                   CI: FR1 + workflows + drift + vendor currency
INSTALL.md                     Windows install for C:\Dev\projects\Skill Core
workflows/process-discovery/
  workflow.toml                5 stages, 1 gate, admission rules
  README.md
  evals/cases.jsonl            15 classification cases
VALIDATION_REPORT_2026-08-08.json
CHANGELOG_ENTRY.md
```

## Installing

Copy into the repository root. No existing paths are overwritten except `skill-core/sources.lock.json`, which was previously absent.

```bash
python scripts/verify_core.py             # FR1 gate — offline, no network
python scripts/validate_workflows.py      # workflow references resolve
python scripts/lock_sources.py --check    # upstream drift (network)
python scripts/vendor_skills.py --dry-run # vendoring is current
```

All four exit 0 against the shipped state. `verify_core.py` was negative-tested: a tampered vendor file and a downgraded license each produce a violation and exit 1.

**Windows / `C:\Dev\projects\Skill Core`:** see `INSTALL.md`. It flags one issue with the repo path before anything else.

## Results

| | |
|---|---|
| Source repos resolved | 9 / 9 |
| Skills locked | **23 / 23** |
| License rejections | 0 |
| Unresolved / ambiguous IDs | 0 |
| Skills vendored | **23 / 23** (91 files) |
| Post-write hash verification | 23 / 23 pass |
| `lock_sources.py --check` | exit 0 |
| `validate_workflows.py` | exit 0 |

## The finding that mattered

`anthropics/skills` **licenses per skill, not per repository.** `skill-creator` is Apache-2.0; `xlsx` in the same repository is all-rights-reserved; `doc-coauthoring` has no license at all and the repository has no root LICENSE.

A repository-level license check — the obvious implementation — would have cleared both rejections and vendored content with no redistribution grant. `lock_sources.py` resolves licenses nearest-first from each skill's own directory upward.

## Decisions applied

All six open items resolved — see `skill-core/GAP_REPORT_v3_RESOLVED.md`.

| Ref | Decision | Result |
|---|---|---|
| A1 | Drop `xlsx`, replace with Apache-2.0 | `gws-sheets` (googleworkspace/cli) |
| A2 | Drop `doc-coauthoring`, replace with Apache-2.0 | `documentation` (anthropics/knowledge-work-plugins) |
| B1 | Rename | `to-prd` → `to-spec` |
| B2 | Rename | `to-issues` → `to-tickets` |
| C1 | Pin variant | `skillopt-sleep` → Codex |
| D1 | Add | `to-questionnaire` |

**Core size is 23**, not 22. Recommend restating PRD FR1 as a property — *every selected skill locked, licensed, vendored* — rather than a fixed count. A required number creates pressure to keep a skill that fails a license check.

## Not done here

- **Projection smoke test** — needs the installer from the main repository. The vendored tree is ready as its input.
- **Push to remote** — the repository still exists in one location only. Your action.
