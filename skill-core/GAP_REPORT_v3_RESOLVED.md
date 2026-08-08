# Source Lock — RESOLVED

**Date:** 2026-08-08 · **Status:** `locked` · **Core size: 23**

All six open items from `GAP_REPORT_v2.md` were decided and applied. The lock is complete: no gaps, no license rejections, all 23 skills vendored and hash-verified.

## Decisions applied

| Ref | Item | Decision | Result |
|---|---|---|---|
| A1 | `xlsx` — all rights reserved | Drop, replace with Apache-2.0 equivalent | → **`gws-sheets`** (googleworkspace/cli, Apache-2.0) |
| A2 | `doc-coauthoring` — no license | Drop, replace with Apache-2.0 equivalent | → **`documentation`** (anthropics/knowledge-work-plugins, Apache-2.0) |
| B1 | `to-prd` — no upstream path | Rename | → **`to-spec`** |
| B2 | `to-issues` — no upstream path | Rename | → **`to-tickets`** |
| C1 | `skillopt-sleep` — 3 variants | Select Codex variant | → pinned `plugins/codex/skills/skillopt-sleep/SKILL.md` |
| D1 | `to-questionnaire` — missing | Add | → added, unblocks process-discovery stage 4 |

### Replacement rationale

**`gws-sheets`** — *"Google Sheets: Read and write spreadsheets."* Covers the spreadsheet read/write role the proprietary `xlsx` skill filled. Same source repository as the already-selected `gws-workflow-email-to-task`, so it adds no new provenance surface.

**`documentation`** — *"Write and maintain technical documentation… API docs, architecture docs, or operational runbooks."* Covers the document-authoring role. Governed by the repository-root Apache-2.0 LICENSE, verified by nearest-first resolution.

Both replacements were license-verified before selection, not after.

## Final state

| Check | Result |
|---|---|
| Source repos resolved | 9 / 9 |
| Skills locked | **23 / 23** |
| License rejections | 0 |
| Unresolved / ambiguous | 0 |
| Skills vendored | **23 / 23** |
| Files vendored | 91 (incl. sibling scripts, references, and per-skill LICENSE) |
| Post-write hash verification | 23 / 23 pass |
| `lock_sources.py --check` | exit 0 — no drift |
| `validate_workflows.py` | exit 0 — 0 failures, 0 warnings |

**License distribution:** MIT 15, Apache-2.0 8.

## Note on core size

The core is now **23**, not the 22 in PRD FR1. The count moved because curation moved: two skills were replaced and one was added to satisfy a workflow dependency.

**Recommend amending FR1 to drop the fixed number.** A required count creates pressure to keep a skill that fails a license check, which is the opposite of what the gate is for. State the requirement as "every selected skill is locked, licensed, and vendored" — a property, not a quantity.

## Schema change

`selection.json` entries now accept an optional `path` field pinning an exact upstream file. Used by `skillopt-sleep` to disambiguate its three platform variants. Lock entries record `path_pinned: true/false` so pinned selections are visible on review.
