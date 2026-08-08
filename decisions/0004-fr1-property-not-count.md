# ADR-0004: FR1 states a property, not a count

- **Status:** ACCEPTED
- **Date:** 2026-08-08
- **Amends:** PRD FR1 (v0.1.0 → v0.2.0)

## Context

PRD v0.1.0 FR1 read: *"Maintain exactly 22 selected core skill IDs."*

During VSA 0.2 source locking, two selected skills failed license verification:

- `xlsx` (anthropics/skills) — *"© 2025 Anthropic, PBC. All rights reserved."* Use governed by a customer agreement, not an open-source grant. Vendoring would redistribute without permission.
- `doc-coauthoring` (anthropics/skills) — no license beside the skill and no repository-root LICENSE. Silence is not permission.

A third skill, `to-questionnaire`, had to be *added* because `workflows/process-discovery` stage 4 depends on it.

Holding the count at 22 would have required one of:

1. Keeping a skill that fails the license gate, to preserve the number.
2. Refusing a needed skill, to preserve the number.
3. Substituting an unrelated skill purely as filler.

All three subordinate a correctness gate to a cosmetic target. The number was doing work it should not do.

## Decision

FR1 states the property every core skill must satisfy, and states no size.

> Every skill in the core is **selected, locked, licensed, and vendored**. No skill is installable unless all four hold. The core has no target size.

Each property is machine-verified:

| Property | Verified by |
|---|---|
| Selected | present in `selection.json` |
| Locked | `sources.lock.json` entry with commit SHA, blob SHA, sha256 |
| Licensed | permissive SPDX resolved nearest-first from the skill's own directory upward |
| Vendored | file under `skill-core/vendor/`, sha256 re-verified from disk after write |

## Consequences

**Positive.** A license failure now has exactly one correct outcome — drop or replace — with no counter-pressure. Core size becomes an observable rather than a constraint. Every clause of FR1 maps to a check that already exists and exits non-zero on failure, satisfying `docs/DOD_POLICY.md`.

**Negative.** "22-skill core" was a memorable shorthand and appears in earlier documents. Those references are now stale; the glossary and PRD carry the correction.

**Neutral.** Core size at v0.2.0 is 23. It will move again, and that is the intended behavior.

## Related

The same reasoning applies wherever a requirement names a quantity that a correctness gate can invalidate. Prefer properties. A count is an outcome.
