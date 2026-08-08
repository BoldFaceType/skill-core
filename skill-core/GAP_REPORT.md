# Source Lock Gap Report

**Generated:** 2026-08-08
**Lock status:** `partially-locked` — 19 of 22 selected skills locked
**Verification method:** git-protocol shallow blobless clone; commit SHA, blob SHA, and sha256 content hash recorded per file

Three selected IDs did not resolve to an exact upstream path. **None have been auto-substituted.** Each requires a human decision. Evidence is recorded below so the decision can be made without re-investigation.

---

## Gap 1 — `to-prd` (mattpocock/skills)

**Status:** unresolved. No path segment named `to-prd` exists at commit `84fdeffd12f2ee307994d1eb6feb48173b6e0502`.

**Evidence.** The repository contains `skills/engineering/to-spec/SKILL.md`, whose frontmatter description reads: *"Turn the current conversation into a spec and publish it to the project issue tracker — no interview, just synthesis..."*

**Assessment.** Almost certainly an upstream rename (`to-prd` → `to-spec`), or the ID was recorded from memory rather than from the repository. The functional role is the same: conversation → structured planning document.

**Proposed resolution:** replace ID `to-prd` with `to-spec`.
**Alternative:** drop from core if the PRD-vs-spec distinction matters to you.

---

## Gap 2 — `to-issues` (mattpocock/skills)

**Status:** unresolved. No path segment named `to-issues` exists at the locked commit.

**Evidence.** The repository contains `skills/engineering/to-tickets/SKILL.md`, described as: *"Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking..."*

**Assessment.** Same pattern as Gap 1 — `issues` → `tickets` is a vocabulary change, not a capability change.

**Proposed resolution:** replace ID `to-issues` with `to-tickets`.

---

## Gap 3 — `skillopt-sleep` (microsoft/SkillOpt)

**Status:** ambiguous. Three distinct blobs exist, one per host platform:

| Path | Blob SHA |
|---|---|
| `plugins/claude-code/skills/skillopt-sleep/SKILL.md` | `22337bafcf4bab9f47c02bfe6d682ce3da2f4252` |
| `plugins/codex/skills/skillopt-sleep/SKILL.md` | `6d6fd16686e451436299b506d88eed96ac1362a9` |
| `plugins/cursor/skills/skillopt-sleep/SKILL.md` | `7caa8fc32fea42d86f39d15f48c58b2b8864bf12` |

The three differ in content; this is not a duplicate-path artifact.

**Proposed resolution:** vendor the **codex** variant, matching the declared primary engine in `workflow.toml` defaults and the Codex/OpenCode projection targets.

**Why this one matters beyond path selection.** Its frontmatter describes the exact loop previously scoped as unbuilt work:

> harvest past sessions → mine recurring tasks → replay through a selected backend → consolidate validated memory + skills behind a held-out gate

This is the acquisition-and-maintenance loop. It is already selected, already upstream, and already gated on held-out validation. It should be treated as the reference implementation for VSA 0.5 rather than something to be reimplemented. See `decisions/0003-skillstore-v1x-archived.md`.

---

## Applying resolutions

Gaps 1 and 2 change `selection.json`, which is a curation decision and is deliberately **not** automated. After editing, re-run:

```bash
python scripts/lock_sources.py
```

The lock file regenerates from scratch; it is never hand-edited.

---

## What did not need a decision

All nine source repositories resolved with permissive licenses — no rejections were required under the "reject incompatible licenses" requirement (TASK_MANIFEST VSA 0.2):

| License | Skills |
|---|---|
| MIT | 11 (mattpocock/skills, vercel-labs/skills, github/awesome-copilot) |
| Apache-2.0 | 8 (anthropics/skills, anthropics/knowledge-work-plugins, openai/skills, googleworkspace/cli, huggingface/skills) |
