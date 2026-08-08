# Source Lock Gap Report

**Generated:** 2026-08-08
**Lock status:** `partially-locked` — **17 of 22** selected skills locked
**Generator:** `scripts/lock_sources.py`
**Verification:** git-protocol shallow blobless clone; commit SHA, blob SHA, and sha256 content hash recorded per file; license resolved nearest-first from the skill's own directory upward

| Outcome | Count |
|---|---|
| Locked | 17 |
| Rejected on license | 2 |
| Unresolved / ambiguous ID | 3 |

Nothing was guessed or substituted. Each open item below is a curation decision requiring your call, with evidence recorded so it can be made without re-investigation.

---

## A. License rejections (2)

These are hard blocks, not naming problems. Both come from `anthropics/skills`, which **licenses per skill rather than per repository** — some skills carry Apache-2.0, others carry all-rights-reserved terms. A repository-level license check would have wrongly cleared both.

### A1 — `xlsx` · REJECTED · proprietary

`skills/xlsx/LICENSE.txt` at commit `f17010c9bb`:

> © 2025 Anthropic, PBC. All rights reserved. LICENSE: Use of these materials (including all code, prompts, assets, files, and other components of this Skill) is governed by your agreement with…

Use is governed by a customer agreement, not an open-source grant. **Vendoring this file into Skill Core would redistribute it**, which the terms do not permit.

**Options:**
1. Drop `xlsx` from the core. It ships with Claude's own environment already; a vendored copy adds little.
2. Reference it without vendoring — record the ID and source, install nothing. Requires a `reference-only` state in the lock schema.
3. Substitute an openly licensed spreadsheet skill.

**Recommended:** option 1. Core size drops to 21.

### A2 — `doc-coauthoring` · REJECTED · no license

`skills/doc-coauthoring/` contains only `SKILL.md`. There is no adjacent `LICENSE.txt`, and `anthropics/skills` has **no repository-root LICENSE**. Absent a grant, there is no redistribution right — silence is not permission.

**Options:**
1. Drop from core.
2. Open an upstream issue asking for clarification, keep selected but unlocked.
3. Reference-only, as A1 option 2.

**Recommended:** option 2, then 1 if unanswered. Core size drops to 20 in the interim.

---

## B. Unresolved IDs (2)

### B1 — `to-prd` → probable rename to `to-spec`

No `to-prd` path exists in `mattpocock/skills` at `84fdeffd12`. The repository contains `skills/engineering/to-spec/SKILL.md`:

> Turn the current conversation into a spec and publish it to the project issue tracker — no interview, just synthesis…

Same functional role. Either an upstream rename or an ID recorded from memory rather than the repository.

**Recommended:** replace `to-prd` with `to-spec` in `selection.json`.

### B2 — `to-issues` → probable rename to `to-tickets`

Same pattern. `skills/engineering/to-tickets/SKILL.md`:

> Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking…

**Recommended:** replace `to-issues` with `to-tickets`.

---

## C. Ambiguous ID (1)

### C1 — `skillopt-sleep` · three platform variants

| Path | Blob SHA |
|---|---|
| `plugins/claude-code/skills/skillopt-sleep/SKILL.md` | `22337bafcf4b…` |
| `plugins/codex/skills/skillopt-sleep/SKILL.md` | `6d6fd16686e4…` |
| `plugins/cursor/skills/skillopt-sleep/SKILL.md` | `7caa8fc32fea…` |

Three distinct blobs — genuinely different content, not a path duplicate. Repository license is MIT, so no license obstacle.

**Recommended:** vendor the **codex** variant, matching the declared default engine and the Codex/OpenCode projection targets.

**Why this one matters beyond path selection.** Its frontmatter describes the loop previously scoped as unbuilt work:

> harvest past sessions → mine recurring tasks → replay through a selected backend → consolidate validated memory + skills behind a held-out gate

That is the acquisition-and-maintenance loop, already upstream, already gated on held-out validation. Treat it as the reference implementation for VSA 0.5 rather than something to reimplement. See `decisions/0003-skillstore-v1x-archived.md`.

---

## D. Clean — no decision required (17)

| License | Count | Sources |
|---|---|---|
| MIT | 11 | mattpocock/skills, vercel-labs/skills, github/awesome-copilot |
| Apache-2.0 | 6 | anthropics/skills (per-skill), anthropics/knowledge-work-plugins, openai/skills, googleworkspace/cli, huggingface/skills |

---

## Applying resolutions

`selection.json` is curation and is deliberately **not** auto-edited. After editing it by hand, regenerate:

```bash
python scripts/lock_sources.py
```

The lock is always regenerated from scratch and never hand-edited. To detect upstream drift later without rewriting:

```bash
python scripts/lock_sources.py --check
```

Exit `0` = clean, `1` = gaps or drift, `2` = hard failure. Suitable as a CI gate.

---

## Projected core size

| Scenario | Size |
|---|---|
| Current locked | 17 |
| + B1, B2, C1 resolved | 20 |
| + A1, A2 dropped | **20 (final)** |
| + A1, A2 reference-only | 22 |

The "22-skill core" in PRD FR1 should be restated as an outcome of curation, not a target. **Recommend amending FR1 to remove the fixed count** — a number that must hold regardless of licensing will eventually pressure a bad call.
