# ADR-0002: Process Discovery becomes a workflow, not a repository

- **Status:** ACCEPTED
- **Date:** 2026-08-08
- **Supersedes:** Process Discovery Automation Engine specification, v0.1.0-alpha, 2026-08-08

## Context

A specification arrived four days after Skill Core v0.1.0 proposing a standalone Process Discovery Automation Engine: ingest desktop recordings or narration, decompose into a step DAG, score each step 1–10 for variability, route to RPA / APA / HITL buckets, and emit scripts, skills, or webhooks.

Comparing it against Skill Core showed roughly 70% duplication:

| PDE component | Already in Skill Core |
|---|---|
| `.agents/skills/` as output target | Projection engine + `.skillstore-projection.json` |
| HITL webhook gates | FR6 approval gates; `runs/<id>` pause |
| Pipeline restart / handoff | `runs/<run-id>/state.json`, stage dirs, `handoff.md` |
| Linear integration | ADR + VSA 0.4, link-only with idempotency keys |
| `skill-creator`, `grill-me`, `handoff`, `to-questionnaire` | Already selected upstream skills |
| Ordered pipeline stages | `workflow.toml` — declarative, not hardcoded |

PRD non-goals for v0.1 explicitly forbid "a second orchestration engine." A standalone PDE is that engine.

Additional defects in the specification as written:

1. **Unverifiable provenance.** The skill table cited "awesome-skills (Open Registry)" and "Anthropic Open Standard" — unresolvable strings, versus `selection.json`'s real repository slugs. Source locking exists to prevent exactly this.
2. **Wrong file shape.** Flat `.agents/skills/<name>.md` rather than `<name>/SKILL.md` directories. Would not be discovered.
3. **Invented and self-contradictory scoring.** A 1–10 variability score produced by a model is a judgment wearing a threshold's clothing. The PRD placed the HITL cutoff at `≥8`; ADR-001 placed it at `<90% confidence`. Two criteria for one bucket.
4. **Roster bloat.** Twelve skills for five stages; four appear nowhere in the flow. A pipeline whose stated goal is halving context carried seven skills of dead context.
5. **Inverted Definition of Done.** Every `[x]` a document, every `[ ]` a test.
6. **The hardest step drawn as an arrow.** Screen recording → structured steps is unsolved; the file watcher only accepts `.txt`/`.md`, meaning the pipeline began after the hard part was done by hand.

## Decision

Fold Process Discovery into Skill Core as `workflows/process-discovery/`. Keep one thing; discard the rest.

**Kept — the sorting decision.** Deciding whether a step becomes a script, a skill, or a human gate is a genuinely useful judgment that nothing else in the ecosystem makes.

**Reframed — three ordered questions replace the numeric score.** First yes wins:

1. Irreversible, financial, published, or clinical? → **GATE**
2. Needs judgment over variable input? → **SKILL**
3. Fixed schema, no judgment? → **SCRIPT**

No match means the step is under-specified and returns to interrogation rather than being forced into a bucket. This removes the fabricated 1–10 scale and the PRD/ADR contradiction in one move.

**Discarded** — the standalone repository, the hardcoded Python pipeline, duplicate gating, duplicate state tracking, duplicate Linear integration, and seven unused skills.

**Bounded** — v0.1 consumes a hand-produced `.md`/`.txt` transcript. Speech-to-text and screen capture are named as out of scope rather than implied by a diagram.

**Kept from PDE that Skill Core lacked:** the insight that *narrated* process capture beats *observed* telemetry. Narration carries intent; logs record only behavior. That is why this workflow takes a transcript rather than mining session history.

## Consequences

**Positive.** No new infrastructure. Gating, resume, and run state come free. The classification rule becomes falsifiable via `evals/cases.jsonl` (15 cases) instead of remaining opinion. Candidate skills land in `candidates/`, outside Skill Core, satisfying TASK_MANIFEST VSA 0.5.

**Negative.** Blocked on VSA 0.2 completion — `validate_workflows.py` currently fails on two unresolved skill references (`to-spec`, `to-questionnaire`). This is correct behavior: the workflow cannot run against skills that are not locked.

**Neutral.** The PDE document is retained as historical context. Nothing is deleted.
