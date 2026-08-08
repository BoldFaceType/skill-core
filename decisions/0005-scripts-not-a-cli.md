# ADR-0005: Scripts, not a CLI package

- **Status:** ACCEPTED
- **Date:** 2026-08-08
- **Amends:** PRD FR9; supersedes the `skillstore` console-script quick start in README v0.1.0

## Context

PRD v0.1.0 FR9 required exposing workflow manifests "through one CLI usable by Marimo and CI," and the v0.1.0 README documented a quick start built on it:

```bash
python -m pip install -e .
skillstore doctor
skillstore validate
skillstore compose engineering-vsa
skillstore install --scope project --platform all --mode copy
```

That package does not exist on disk. A filesystem search of `C:\Dev` found no `skillstore` package, no `pyproject.toml`, and no `selection.json` outside this repository. The documented interface was aspirational.

Its absence was treated for several milestones as a blocker on FR7 (projection). That was wrong twice over. First, the missing component belongs to Skill Core, not to the archived SkillStore v1.x, so deprecation did not remove the need. Second and more importantly: **the projection is a file copy.** A packaged CLI with `doctor` / `validate` / `compose` / `install` subcommands, an editable install step, and a build backend is machinery the task does not require.

`vendor_skills.py` already did most of the work — copy files, verify each against the lock. The projection is the same operation with a different destination plus a manifest of what it owns.

## Decision

Skill Core's interface is a set of stdlib-only scripts under `scripts/`. There is no package, no `pyproject.toml`, no editable install, no console entry points.

| v0.1.0 command | Replacement |
|---|---|
| `skillstore doctor` | *(dropped — diagnosed nothing the gates do not)* |
| `skillstore validate` | `scripts/verify_core.py`, `scripts/validate_workflows.py` |
| `skillstore compose <id>` | `workflows/<id>/workflow.toml` is already the composition |
| `skillstore install` | `scripts/project_skills.py` |

FR9 is restated: **workflow manifests are exposed through scripts that Marimo, CI, and the shell all invoke identically.** One interface, three callers — the original intent, without the packaging.

## Consequences

**Positive.** No dependency to install before verification runs; CI needs only a Python interpreter. Every script is stdlib-only and independently runnable. Adding a capability means adding a file, not extending a command tree. The `pip install -e .` step disappears from the quick start, removing the most common first-run failure.

**Negative.** No `skillstore` on `PATH`; commands are `python scripts/<name>.py`. Slightly more typing, and no shared argument parsing across scripts — each defines its own flags. Accepted: five scripts do not justify a framework.

**Neutral.** If the script count grows past roughly a dozen, or several need shared state, revisit. That threshold is not close.

## Related

This is the same failure mode recorded in ADR-0003 for SkillStore v1.x: building infrastructure that the platform, or the filesystem, already provides. Skill Core is not a runtime (PRD non-goals) and it does not need to be a package either. It is a versioned tree plus verification scripts.
