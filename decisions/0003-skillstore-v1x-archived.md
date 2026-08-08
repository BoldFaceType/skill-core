# ADR-0003: SkillStore v1.x is archived, not migrated

- **Status:** ACCEPTED
- **Date:** 2026-08-08
- **Applies to:** SkillStore v1.0.0 – v1.4.0 (2025-10-05 → 2026-03-26)

## Context

SkillStore v1.x was a Python package implementing a 3-tier Primitive/Functional/Module hierarchy over SQLite, with a Voyager learning loop (extract skills from successful runs), a self-healing refiner, adaptive model selection, and token-economics tracking. v1.4.0 added an LLM Signature Framework integration as its code-generation engine.

Despite the shared name, it shares **no code and no concepts** with Skill Core beyond the word "skill." Skill Core is not its successor version.

### Why it is superseded

The SKILL.md standard absorbed four of the six concerns v1.x owned:

| Concern | v1.x built | Status |
|---|---|---|
| Representation | 3-tier hierarchy, code strings in SQLite | Absorbed — folder + frontmatter + progressive disclosure |
| Discovery | Jaccard word overlap; chromadb declared but unused | Absorbed — model-invoked frontmatter matching |
| Distribution | CLI + PyPI | Absorbed — plugins and skill directories |
| Execution | `exec()` in-process | Absorbed — host tools with real permissioning |
| **Acquisition** | Voyager extraction loop | Was the remaining value |
| **Maintenance** | Refiner, success_rate telemetry | Was the remaining value |

### Why it is not worth repairing

Verified defects in the v1.4.0 artifact:

- `voyager/economics.py` and `voyager/selector.py` are imported at module scope but were never written — the package raises `ImportError` on first import.
- Token savings are structurally zero: extraction sets `avg_tokens_if_fresh = avg_tokens`, so `tokens_saved` is always `0`. The headline feature cannot work as written.
- `_execute_code()` is a bare `exec()` on model-generated code, in-process, with full interpreter access.
- `SkillRefiner.max_attempts` is dead — the loop returns unconditionally on the first iteration, and the repair is never validated. A broken fix is accepted as a fix.
- No tests exist, while the CHANGELOG documents "Fixes" and "Security" sections.

### Why the remaining value is also covered

The two live concerns — acquisition and maintenance — are addressed upstream by `skillopt-sleep` (microsoft/SkillOpt, MIT), already in `selection.json`. Its own description:

> harvest past sessions → mine recurring tasks → replay through a selected backend → consolidate validated memory + skills behind a held-out gate

A held-out validation gate is precisely what v1.x's refiner lacked. Reimplementing this locally would duplicate an MIT-licensed, already-selected skill.

This also supersedes two earlier local designs for the same loop: the `skilllog` / `skillpromote` pair, and the Resolver-agent / SkillOpt-pipeline framing from the Filesystem-As-State canon. Three designs, one problem, one upstream answer.

## Decision

Tag SkillStore v1.x as `v1.4.0-alpha` and archive it. **Do not migrate, repair, or harvest code from it.**

Carry forward two ideas as principles, encoded in `workflows/process-discovery/workflow.toml` under `[admission]`:

1. **`min_recurrence = 2`** — from `should_extract()`. Do not create an artifact for something seen once.
2. **`max_description_overlap = 0.6`** — the anti-duplication gate. Scored 0.9 on the original vetting pass and remains the mechanism that prevents a library of near-identical auto-generated skills.

A third principle, `require_declared_inputs = true`, comes from v1.x's parameterization discipline.

## Consequences

**Positive.** No migration cost. No security liability inherited. Three competing acquisition designs collapse to one upstream skill.

**Negative.** Work is retired without shipping. The parameter-substitution and extraction code is discarded rather than reused.

**Neutral.** The v1.4.0 artifact and its analysis are retained as history. The `[admission]` block is the migration.

**Related.** The LLM Signature Framework is *relocated*, not retired: typed prompts with Pydantic validation and retry still earn their keep against local small models (LM Studio / Ollama), where structured output is unreliable. Keep it as a standalone local-inference utility, outside the skill loop.
