# Product Requirements Document: Skill Core

Version: 0.2.0
Date: 2026-08-08
Status: VSA 0.2 complete
Supersedes: PRD v0.1.0 (2026-08-04, titled "SkillStore v3")

## Problem

Jeremie needs one versioned store for exact upstream Agent Skills, reusable workflow compositions, deterministic evaluation, and installation across Codex, OpenCode, GitHub, and a Marimo control surface. Copying and editing skills separately for each platform creates drift, context bloat, and unclear ownership.

## Product statement

Skill Core is a filesystem-as-state skill store and workflow compiler. It preserves exact upstream skills, composes them through declarative workflow manifests, projects them into shared Agent Skills discovery paths, and records durable run/evaluation state as files.

It is **not a runtime**. Execution belongs to hosts.

## Users

- Primary operator: Jeremie.
- Secondary operators: weaker local/cloud coding agents executing bounded workflow stages.

## Functional requirements

**FR1 — Core integrity.** Every skill in the core is *selected, locked, licensed, and vendored*. No skill is installable unless all four hold:

| Property | Verified by |
|---|---|
| **Selected** | present in `skill-core/selection.json` |
| **Locked** | entry in `sources.lock.json` with commit SHA, blob SHA, sha256 content hash |
| **Licensed** | permissive SPDX id resolved from the license governing *that skill*, nearest-first from its own directory upward |
| **Vendored** | file present under `skill-core/vendor/`, sha256 re-verified from disk after write |

The core has **no target size**. Its size is an outcome of curation, not an input to it.

> *Rationale.* v0.1.0 stated FR1 as "maintain exactly 22 selected core skill IDs." During VSA 0.2, two selected skills failed license verification — `xlsx` (all rights reserved) and `doc-coauthoring` (no license found). A fixed count creates pressure to retain a skill that fails a gate in order to hold the number, which inverts the gate's purpose. The count is now 23; it will move again. See `decisions/0004-fr1-property-not-count.md`.

**FR2 — Lock before install.** Record source repository, path, commit, blob SHA, content hash, and license for each vendored skill before it is installed. Locks are generated, never hand-edited.

**FR3 — Immutability.** Never modify files inside Skill Core. Skill-Core-specific candidates live outside it.

**FR4 — Declarative composition.** Define workflows as ordered stages referencing exact core IDs. Workflows are data, not code.

**FR5 — Durable outputs.** Every workflow stage declares a durable output. The next stage reads the file, not the prior conversation.

**FR6 — Approval gates.** Support stages that halt until a human approves, leaving state on disk.

**FR7 — Shared projection.** Generate project and user installations under `.agents/skills`, owning only declared paths and preserving unmanaged user skills.

**FR8 — Optional host wrappers.** Generate OpenCode command entrypoints without duplicating skills.

**FR9 — One CLI.** Expose workflow manifests through a single CLI usable by Marimo and CI.

**FR10 — Explicit tracker ownership.** Keep GitHub and Linear ownership explicit per workflow.

**FR11 — Local evaluation.** Evaluate workflows with local cases/rubrics and shared evaluation scripts.

**FR12 — Run state as files.** Preserve run state under `runs/<run-id>/`.

**FR13 — Drift detection.** Provide a non-mutating check that fails when locked content diverges from upstream, suitable as a CI gate.

## Non-functional requirements

- **Local-first.** No SaaS dependency in the critical path. Source resolution uses the git protocol, not an authenticated API.
- **Reproducible.** Lock generation is idempotent; identical upstream state yields identical output.
- **Additive.** Tooling never deletes what it did not create.
- **Honest status.** Status labels name their own gaps (`partially-locked`, `selected-not-locked`). Self-authored "APPROVED" is not a status. See `docs/DOD_POLICY.md`.

## Non-goals for v0.x

- Automatic fetching of unverified upstream skill content.
- Autonomous GitHub or Linear mutation.
- A second orchestration engine inside Marimo.
- Automatic skill promotion without human approval.
- Bidirectional GitHub/Linear field synchronization.
- **A skill execution runtime.** Hosts execute; Skill Core stores and composes.

## Success criteria

- Repository validation passes deterministically.
- All workflow stage skill IDs resolve to locked core entries.
- One install command materializes a shared projection without deleting unmanaged user skills.
- Codex/OpenCode/GitHub consume the same project skill tree.
- Marimo reads the same manifests and invokes the same CLI.
- **FR1 holds for every core skill, verified by tooling rather than assertion.**

## Status at v0.2.0

| Requirement | State | Evidence |
|---|---|---|
| FR1 | ✅ 23/23 | `sources.lock.json` status `locked`; `vendor_skills.py` 23/23 verified |
| FR2 | ✅ | `scripts/lock_sources.py` |
| FR3 | ✅ | vendored copies unmodified; candidates directed to `candidates/` |
| FR4 | ✅ | `workflows/process-discovery/workflow.toml` |
| FR5 | ✅ | validated by `validate_workflows.py` |
| FR6 | ✅ declared | gate stage present; runtime pause is VSA 0.3 |
| FR7 | ⬜ | installer exists in main repo; smoke test not yet run against vendored tree |
| FR8–FR12 | ⬜ | VSA 0.3–0.5 |
| FR13 | ✅ | `lock_sources.py --check`, exit 0 |
