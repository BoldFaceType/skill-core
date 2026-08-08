# Process Discovery

Turn a narrated process transcript into steps sorted into **scripts**, **candidate skills**, and **human gates**.

Supersedes the standalone Process Discovery Automation Engine spec (2026-08-08). See `decisions/0002-process-discovery-as-workflow.md`.

## Input boundary

v0.1 consumes a **hand-produced** `.md` or `.txt` transcript. Speech-to-text and screen capture are out of scope. This is stated rather than implied: the original spec drew "screen recording → structured steps" as an arrow, which hid the hardest part of the problem.

Talk through the process out loud, transcribe it however you like, save the text. That is the input.

## The sorting rule

Three questions per step, in order. **First yes wins.**

| # | Question | Result |
|---|---|---|
| 1 | Irreversible, financial, published, or clinical? | **GATE** |
| 2 | Needs judgment over variable input? | **SKILL** |
| 3 | Fixed schema, no judgment? | **SCRIPT** |

No match → **under-specified**. Return it to interrogation. Do not force a bucket.

Order matters. "Draft a reply to the customer" is a SKILL; "send the reply" is a GATE. Splitting them is the point — the reversible half can be automated, the irreversible half cannot.

There is deliberately **no numeric variability score**. A 1–10 rating produced by a model is a judgment wearing a threshold's clothing, and the original spec's PRD (`≥8`) and ADR (`<90% confidence`) disagreed on where the cutoff sat.

## Stages

| # | Stage | Skill | Output |
|---|---|---|---|
| 1 | decompose | `domain-modeling` | `steps.md` |
| 2 | interrogate | `grill-me` | `open-questions.md` |
| 3 | sort | `to-spec` | `classification.md` |
| 4 | **approve** (gate) | `to-questionnaire` | `approved.md` |
| 5 | emit | `skill-creator` | `manifest.md` |

Each stage reads the prior stage's **file**, not the prior conversation. That bounds context and makes resume/retry work.

## Where output goes

```
scripts/generated/<process>/<step>.py      AST-validated before write
candidates/<process>/<step>/SKILL.md       NEVER into skill-core/
stages/05-emit/gates.md                    declarations only; no webhook writes in v0.1
```

Candidate skills live **outside** Skill Core by design (TASK_MANIFEST VSA 0.5). Nothing enters Skill Core without source locking.

## Admission rules

From `[admission]` in `workflow.toml`, carried forward from SkillStore v1.x as principles:

- `min_recurrence = 2` — seen twice before it becomes an artifact
- `max_description_overlap = 0.6` — reject near-duplicates of existing core skills
- `require_declared_inputs = true` — no reliance on ambient context

## Evaluation

`evals/cases.jsonl` holds 15 classification cases with expected buckets and rationale, including deliberate near-misses (c12 vs c13: grouping by an existing field is a SCRIPT, deciding which tickets are the same bug is a SKILL) and two under-specified cases that must *not* be forced into a bucket.

This is what makes the sorting rule falsifiable rather than an opinion.

## Status

**Blocked.** `scripts/validate_workflows.py` fails on two unresolved skill references:

- `to-spec` — pending GAP_REPORT B1 (rename from `to-prd`)
- `to-questionnaire` — absent from `selection.json`; verified present upstream

This is correct behavior. The workflow cannot run against skills that are not locked. Resolve VSA 0.2 first.
