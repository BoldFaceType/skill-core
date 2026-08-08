# Definition of Done Policy

## The rule

**No checklist item may be marked `[x]` unless something automated verifies it.**

A document existing is not evidence that the thing it describes works.

## Why this exists

Two prior artifacts in this ecosystem were finished as documents and abandoned as systems:

- **SkillStore v1.4.0** — CHANGELOG announced "Added," "Fixed," and "Security" sections for a package that raised `ImportError` on first import. Two modules imported at module scope were never written. Zero tests existed. The headline feature (token savings) computed a constant zero by construction.
- **Process Discovery Engine v0.1.0-alpha** — every `[x]` was a document; every `[ ]` was a test. Status read `APPROVED` on a self-authored rough outline.

The failure mode is consistent: work proceeds until the remaining tasks are tedious rather than interesting, then a new architecture appears instead of the boring part getting done. Marking documentation `[x]` makes the abandonment invisible.

## What counts as verification

| Claim | Acceptable evidence |
|---|---|
| A file exists | A test asserting its presence |
| Code runs | A test importing and calling it |
| A schema is valid | A validation run over a fixture |
| A skill is vendored | Lock entry with commit + blob SHA + content hash |
| A license is compatible | Recorded SPDX id resolved from the license file governing that skill |
| An install works | Smoke test counting materialized skills |
| A gate pauses | Test asserting the run halts and state persists |

## What does not count

Writing the document. Reading the document. A plan to test. A passing test that asserts nothing (`assert True`). Manual confirmation not captured in a file.

## Status vocabulary

Use honest compound labels. `partially-locked`, `pass-with-known-source-lock-gap`, and `selected-not-locked` are good — they name the gap in the status itself. `APPROVED` on self-authored work is not a status.

## Enforcement

- `scripts/lock_sources.py --check` exits non-zero on drift or gaps → CI gate.
- Any checklist row marked `[x]` should name its verifying test or artifact inline.
- Validation reports state counts, not adjectives: `core_skills_materialized: 0` is worth more than "projection working."
