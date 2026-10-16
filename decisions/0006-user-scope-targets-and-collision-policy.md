# ADR-0006: User-scope projection targets, collision policy, and sync

- **Status:** IMPLEMENTED-LOCAL, NOT PUSHED (29 tests green; real-repo projection byte-identical; end-to-end run on a throwaway HOME)
- **Date:** 2026-10-16
- **Amends:** ADR-0005 (still scripts, not a CLI); extends `scripts/project_skills.py`

## Context

The goal is PromptKit_v2's behavior for skills: run one command on whatever machine you are on and the latest `SKILL.md` set lands where each agent reads it. PromptKit's `scripts/sync_agents.py` does this for instruction files. Three differences matter for skills:

1. **Destinations.** Verified against current docs: Claude Code reads `~/.claude/skills/<name>/SKILL.md`; Codex reads `$HOME/.agents/skills` (no `~/.codex/skills` is documented). `project_skills.py --scope user` already wrote `~/.agents/skills`, so only `~/.claude/skills` was missing.
2. **Skills are directories, not files.** PromptKit overwrites each target file blindly. For a directory that destroys a user's own skill with the same name. `~/.claude/skills` is shared with hand-made skills, plugin-synced skills (`synced/`), and other tools.
3. **No pull.** PromptKit relies on CI plus a manual `git pull`. The sync command here pulls.

The original `copytree` call crashed on any existing same-name directory, and refresh deleted owned skills before copying (a crash mid-way lost a skill). In link mode a refresh refused its own symlinks, because `resolve()` leaves the projection root by design.

## Decision

Extend `project_skills.py` rather than add a script or a framework (Rule of One).

**Targets.** `--targets claude,agents` projects to `~/.claude/skills` and `~/.agents/skills`. Default (no flags) is unchanged: `<repo>/.agents/skills`. Each root keeps its own manifest.

**Sync.** `--sync` runs `git pull --ff-only` on the repo, then projects to `claude,agents`. A failed pull aborts before anything is projected. `--dry-run --sync` does not pull. The repo root comes from the script's own location (or `--root` / `SKILLCORE_ROOT`), so it runs from any directory; PromptKit's script requires the repo root as cwd and defaults `DEV_ROOT` to `C:\Dev`.

**Collision policy.** A name that exists and is not in the manifest is never modified.

| Destination state | Action |
|---|---|
| Missing | Stage, swap in, record |
| In manifest, unchanged | Leave alone (`unchanged`) |
| In manifest, stale | Stage, swap in, record |
| Unmanaged, whole tree identical to vendor | Skip; `--adopt` records it without writing |
| Unmanaged, anything else (incl. symlink, case-clash) | Skip, warn, exit 2; `--force` backs up first |
| Reserved or unsafe id | Refuse, exit 1 |

- **Identity is the whole tree, not SKILL.md.** The lock hashes SKILL.md alone; a vendored skill also carries `references/`, `agents/`, `scripts/`. SKILL.md-only equality would adopt a directory with foreign extra files.
- **Backups live outside every skills root** (`~/.skillstore-backup/<utc>/<target>/<id>`). A `<id>.bak` sibling inside the root would be loaded by Claude Code as a skill and listed twice by Codex, which does not merge duplicate names.
- **Writes are staged and swapped.** New content is built in `<root>/../.skillstore-stage`, the old copy is parked, then `os.replace`. A failed swap restores the old copy; leftover stage debris is cleared on the next run. A symlinked destination is unlinked, never followed.
- **Reserved ids:** `synced` (Claude Code's claude.ai sync folder) and `anthropic-skills` are refused, as are dot-prefixed, path-separator, and case-folded duplicate ids.
- **Exit codes:** 0 ok, 1 refused or failed, 2 ran but skipped collisions. Failure outranks collision.
- **Manifest** is rewritten only when owned set, mode, scope, or target changes, so the committed `.agents/skills/.skillstore-projection.json` does not churn.
- Entrypoint skills are written as bytes (LF); text-mode writes would emit CRLF on Windows and break byte comparison.

## Not decided here (out of scope, WIP limit)

- **Marimo skills** (`marimo-team/skills`, Apache-2.0): candidate for `selection.json` + vendoring. Per-skill contents not yet inspected.
- **honey** (`Green-PT/honey-for-devs`): not a plain SKILL.md folder; it ships hooks, a Node CLI, and a codec. It stays a plugin, outside skill-core.
- **superpowers:** stays a plugin. Vendoring it would create a second source of truth.

## Verification (DoD: each claim names its evidence)

| Claim | Evidence |
|---|---|
| Both targets projected, manifests correct | `tests/test_project_skills.py::TestTargets::test_fresh_install_both_targets` |
| Re-run changes nothing | `TestTargets::test_rerun_is_noop` |
| Collision skipped, bytes untouched, exit 2 | `TestCollisions::test_collision_skips_and_leaves_bytes` |
| Adopt requires whole-tree equality | `test_adopt_identical_tree`, `test_same_skill_md_extra_file_is_collision_even_with_adopt` |
| Force backs up outside all roots, no phantom skill | `test_force_backs_up_outside_every_skills_root` |
| Case-clash is a collision | `test_case_clash_is_collision` |
| Reserved / duplicate / traversal ids refused | `TestRefusals` (4 tests) |
| Symlink fallback; link refresh; symlink dest not followed | `TestSwap::test_symlink_failure_falls_back_to_copy`, `test_link_mode_refresh_keeps_source_intact`, `test_owned_symlink_dest_unlinked_not_followed` |
| Crash before or during swap loses nothing | `test_crash_before_swap_leaves_old_skill`, `test_failed_second_rename_restores_old` |
| Failed pull projects nothing | `TestSync::test_pull_failure_aborts_before_projecting`; manual run against a non-git root |
| Dry-run writes nothing | `TestCollisions::test_dry_run_touches_nothing` |

Not yet verified: Windows (symlink fallback is tested by patching `symlink_to`, not on a real Windows host), and macOS case-insensitive behavior (the case-clash test passes on a case-sensitive filesystem; its assertion is written to hold on both).

## Consequences

**Positive.** One command per machine; unmanaged skills are never lost; a crash cannot delete a skill; CI still reproduces the committed projection byte-for-byte.

**Negative.** `--sync` needs `git` on PATH and a fast-forwardable checkout (a diverged local branch aborts rather than merging, by design). Skills already present in `~/.claude/skills` need a one-time `--adopt` or `--force` decision.
