#!/usr/bin/env python3
"""
project_skills.py -- Materialize the shared Agent Skills projection.

Copies vendored Skill Core skills into one or more skills directories and
generates one entrypoint skill per workflow. Targets:

    project (default)   <repo>/.agents/skills
    agents              ~/.agents/skills   Codex, OpenCode, GitHub agents (user scope)
    claude              ~/.claude/skills   Claude Code (user scope)

Ownership is explicit. Each projection root keeps a manifest
`.skillstore-projection.json` recording every path this script created. A skill
installed by hand -- or by any other tool -- is never modified or deleted.

A skill name that already exists and is not in the manifest is a COLLISION. The
default is to skip it, say so, and exit 2. Nothing unmanaged is ever overwritten.
  --adopt   record an unmanaged dir as ours, only if its whole tree is
            byte-identical to the vendored tree (the lock hashes SKILL.md
            alone, so SKILL.md-only equality is not enough)
  --force   move the unmanaged dir to ~/.skillstore-backup/<utc>/<target>/<id>
            (outside every skills root, so no tool loads it as a skill), then
            project

Writes are staged beside the root (`<root>/../.skillstore-stage`) and swapped in
with os.replace; the old copy is parked until the new one is in place and is
restored if the swap fails. There is no CLI framework here on purpose: the
projection is a file copy (ADR-0005).

Usage:
    python scripts/project_skills.py                        # <repo>/.agents/skills
    python scripts/project_skills.py --targets claude,agents
    python scripts/project_skills.py --sync                 # git pull --ff-only, then
                                                            # project to claude+agents
    python scripts/project_skills.py --targets claude --dry-run
    python scripts/project_skills.py --targets claude --adopt
    python scripts/project_skills.py --targets claude --force
    python scripts/project_skills.py --mode link            # symlink (dev)
    python scripts/project_skills.py --prune                # remove what we own

The repo root defaults to this script's parent directory (override: --root or
SKILLCORE_ROOT), so it can be run from any directory on any machine.

Exit 0 = projection matches the lock, 1 = refused or failed, 2 = ran, but one or
more collisions were skipped and need a decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

LOCK = "skill-core/sources.lock.json"
WORKFLOWS = "workflows"
MANIFEST_NAME = ".skillstore-projection.json"
STAGE_NAME = ".skillstore-stage"
BACKUP_NAME = ".skillstore-backup"
REPO_ROOT = Path(__file__).resolve().parent.parent

# Claude Code reserves skills/synced for claude.ai account sync and refuses any
# folder named anthropic-skills outside a plugin.
RESERVED = {"synced", "anthropic-skills"}

TARGETS = {
    "claude": (".claude", "skills"),
    "agents": (".agents", "skills"),
}

NEW, OWNED, ADOPTABLE, COLLISION = "new", "owned", "adoptable", "collision"


# --------------------------------------------------------------------- roots

def projection_roots(scope: str, targets: list[str]) -> list[tuple[str, Path]]:
    """(label, root) pairs. Project scope lives in the repo; user scope in $HOME."""
    if targets:
        return [(t, Path.home().joinpath(*TARGETS[t])) for t in targets]
    if scope == "user":
        return [("agents", Path.home().joinpath(*TARGETS["agents"]))]
    return [("project", Path(".agents") / "skills")]


def parse_targets(raw: str) -> list[str]:
    out: list[str] = []
    for t in (x.strip() for x in raw.split(",")):
        if not t:
            continue
        if t not in TARGETS:
            raise ValueError(f"unknown target '{t}' (choose from {', '.join(TARGETS)})")
        if t not in out:
            out.append(t)
    if not out:
        raise ValueError("--targets is empty")
    return out


# ------------------------------------------------------------------ manifest

def read_manifest(root: Path) -> dict:
    path = root / MANIFEST_NAME
    if not path.exists():
        return {"schema_version": 1, "owned": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # A malformed manifest means we cannot prove ownership. Refuse rather
        # than guess -- guessing here means deleting someone else's skills.
        raise SystemExit(f"refused: manifest unreadable at {path}: {e}")


def write_manifest(root: Path, owned: list[str], scope: str, mode: str,
                   target: str, previous: dict) -> None:
    """Rewrite only when something that matters changed, so a manifest committed
    to git does not churn on every no-op run."""
    owned = sorted(owned)
    if (previous.get("owned") == owned and previous.get("mode") == mode
            and previous.get("scope") == scope and previous.get("target") == target):
        return
    payload = {
        "schema_version": 1,
        "generator": "scripts/project_skills.py",
        "generated": date.today().isoformat(),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": scope,
        "target": target,
        "mode": mode,
        "owned": owned,
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ----------------------------------------------------------------- id safety

def id_problem(name: str) -> str | None:
    """Why this skill id may not be projected, or None if it is fine."""
    if not name or name in (".", "..") or Path(name).name != name or "\\" in name:
        return "unsafe id (must be a single path component)"
    folded = name.casefold()
    if folded in RESERVED or folded.startswith("anthropic-skills:"):
        return "reserved id"
    if folded == MANIFEST_NAME.casefold() or name.startswith("."):
        return "unsafe id (dot-prefixed or manifest name)"
    return None


# ------------------------------------------------------------ tree comparison

def tree_digest(p: Path) -> dict[str, str] | None:
    """relative posix path -> sha256 for every file under p.

    None when p holds any symlink: we cannot call such a tree identical to a
    vendored copy, so the caller treats it as a collision.
    """
    out: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(p, followlinks=False):
        for d in dirnames:
            if (Path(dirpath) / d).is_symlink():
                return None
        for f in filenames:
            fp = Path(dirpath) / f
            if fp.is_symlink():
                return None
            out[fp.relative_to(p).as_posix()] = hashlib.sha256(fp.read_bytes()).hexdigest()
    return out


def classify(root: Path, name: str, expected: dict[str, str] | None,
             owned: set[str], existing_fold: dict[str, str]) -> tuple[str, str]:
    """NEW | OWNED | ADOPTABLE | COLLISION, with a human reason for collisions."""
    clash = existing_fold.get(name.casefold())
    if clash is not None and clash != name:
        # Case-insensitive filesystems (Windows, macOS) would write into it.
        return COLLISION, f"case-clash with existing '{clash}'"
    dst = root / name
    if not dst.exists() and not dst.is_symlink():
        return NEW, ""
    if name in owned:
        return OWNED, ""
    if dst.is_symlink() or not dst.is_dir():
        return COLLISION, "unmanaged symlink or file"
    if expected is not None and tree_digest(dst) == expected:
        return ADOPTABLE, "identical to vendored tree"
    return COLLISION, "unmanaged dir with different content"


def is_current(dst: Path, expected: dict[str, str] | None, src: Path | None,
               mode: str) -> bool:
    """True when an owned dest already matches what we would project."""
    if mode == "link" and src is not None:
        return dst.is_symlink() and dst.resolve() == src.resolve()
    if dst.is_symlink() or not dst.is_dir():
        return False
    return expected is not None and tree_digest(dst) == expected


# --------------------------------------------------------------- file actions

def remove_owned(root: Path, owned: list[str], dry: bool) -> int:
    """
    Remove only paths this script previously created.

    Anything not listed in the manifest survives, which is what makes it safe to
    run against a directory the user also installs skills into by hand. A name
    must be a single path component: that is the containment check. (Resolving
    the target is wrong here -- a link-mode symlink resolves outside the root by
    design.)
    """
    removed = 0
    for rel in owned:
        if Path(rel).name != rel or rel in ("", ".", ".."):
            print(f"  refused (not a single path component): {rel}", file=sys.stderr)
            continue
        target = root / rel
        if not target.exists() and not target.is_symlink():
            continue
        if dry:
            print(f"  would remove {rel}", file=sys.stderr)
        elif target.is_symlink() or target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target)
        removed += 1
    return removed


def stage_new(stage: Path, name: str, src: Path | None, body: bytes | None,
              mode: str) -> Path:
    """Build the new copy under stage/new/<name>. Never touches the live root."""
    new = stage / "new" / name
    new.parent.mkdir(parents=True, exist_ok=True)
    if body is not None:
        new.mkdir()
        (new / "SKILL.md").write_bytes(body)  # bytes: no CRLF translation on Windows
        return new
    assert src is not None
    if mode == "link":
        try:
            new.symlink_to(src.resolve(), target_is_directory=True)
            return new
        except OSError:
            # Windows without Developer Mode cannot symlink unprivileged.
            print(f"  symlink unavailable, copying: {name}", file=sys.stderr)
    shutil.copytree(src, new)
    return new


def swap_in(new: Path, dst: Path, stage: Path) -> None:
    """Replace dst with new. The old copy is parked, not deleted, until the new
    one is in place, and restored if the swap fails."""
    parked = None
    if dst.exists() or dst.is_symlink():
        parked = stage / "old" / dst.name
        parked.parent.mkdir(parents=True, exist_ok=True)
        os.replace(dst, parked)  # renames a symlink itself; never follows it
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.replace(new, dst)
    except BaseException:
        if parked is not None:
            os.replace(parked, dst)
        raise


def backup_unmanaged(dst: Path, label: str, name: str, stamp: str) -> Path:
    """Move an unmanaged skill out of every skills root before replacing it."""
    base = Path.home() / BACKUP_NAME / stamp / label / name
    dest, n = base, 0
    while dest.exists() or dest.is_symlink():
        n += 1
        dest = base.with_name(f"{name}-{n}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(dst), str(dest))
    return dest


# ----------------------------------------------------------------- workflows

def load_workflows() -> list[dict]:
    """Read workflow manifests. Returns [] if tomllib is unavailable."""
    try:
        import tomllib
    except ImportError:
        print("  warning: tomllib unavailable; skipping entrypoints", file=sys.stderr)
        return []
    out = []
    for path in sorted(Path(WORKFLOWS).glob("*/workflow.toml")):
        with open(path, "rb") as f:
            out.append(tomllib.load(f))
    return out


def entrypoint_body(wf: dict) -> str:
    """
    Generate the entrypoint skill for one workflow.

    This is a generated view over workflow.toml, not a new core skill. It exists
    so an agent can discover the composition; the stage instructions still live
    in the exact vendored skills it references.
    """
    meta = wf["workflow"]
    stages = sorted(wf.get("stage", []), key=lambda s: s["order"])
    desc = meta.get("description", "").replace('"', "'")

    lines = [
        "---",
        f"name: workflow-{meta['id']}",
        f'description: "{desc} Ordered stages over exact Skill Core skills."',
        "---",
        "",
        f"# {meta.get('title', meta['id'])}",
        "",
        f"{meta.get('description', '')}",
        "",
        "> Generated from `workflows/"
        f"{meta['id']}/workflow.toml` by `scripts/project_skills.py`.",
        "> Edit the manifest, not this file.",
        "",
        "## Stages",
        "",
    ]
    for s in stages:
        gate = " **(approval gate)**" if s.get("gate") else ""
        lines.append(f"{s['order']}. **{s['id']}**{gate} - skill `{s.get('skill','-')}`")
        lines.append(f"   - output: `{s.get('output','-')}`")
        first = (s.get("description", "").strip().splitlines() or [""])[0]
        if first:
            lines.append(f"   - {first}")
        lines.append("")
    lines += [
        "Each stage reads the previous stage's output file, not the whole prior",
        "conversation. That bounds context and makes resume and retry possible.",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------- sync

def git_pull(repo: Path) -> tuple[bool, str]:
    """Fast-forward only: never merges, never rewrites local history."""
    try:
        r = subprocess.run(["git", "-C", str(repo), "pull", "--ff-only"],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return False, str(e)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# ------------------------------------------------------------------ project

def project_one(label: str, root: Path, scope: str, args, lock: dict,
                workflows: list[dict], stamp: str) -> tuple[list[str], list[str]]:
    """Project into one root. Returns (failures, skipped-collisions)."""
    manifest = read_manifest(root)
    previously_owned = set(manifest.get("owned", []))
    stage = root.parent / STAGE_NAME
    dry = args.dry_run
    failures: list[str] = []
    skipped: list[str] = []
    adopted: list[str] = []
    forced: list[str] = []
    owned: list[str] = []

    print(f"\n[{label}] {root}", file=sys.stderr)
    existing = list(root.iterdir()) if root.exists() else []
    existing_fold = {p.name.casefold(): p.name for p in existing}
    unmanaged_before = {p.name for p in existing
                        if p.name != MANIFEST_NAME and p.name not in previously_owned}

    if not dry and stage.exists():
        shutil.rmtree(stage, ignore_errors=True)  # debris from a crashed run

    items: list[tuple[str, str, Path | None, dict | None, bytes | None, dict | None]] = []
    for s in lock["skills"]:
        src = Path(s["vendor_path"]).parent
        items.append(("core", s["id"], src, s, None, None))
    for wf in workflows:
        body = entrypoint_body(wf).encode("utf-8")
        items.append(("entry", f"workflow-{wf['workflow']['id']}", None, None, body, wf))

    seen: dict[str, str] = {}
    try:
        for kind, name, src, s, body, _wf in items:
            problem = id_problem(name)
            if problem:
                failures.append(f"{name}: refused, {problem}")
                continue
            if name.casefold() in seen:
                failures.append(f"{name}: refused, collides with '{seen[name.casefold()]}' "
                                f"when case is ignored")
                continue
            seen[name.casefold()] = name
            if kind == "core" and not src.is_dir():
                failures.append(f"{name}: vendor dir missing at {src}")
                continue

            if kind == "core":
                expected = tree_digest(src)
            else:
                expected = {"SKILL.md": hashlib.sha256(body).hexdigest()}

            state, why = classify(root, name, expected, previously_owned, existing_fold)
            dst = root / name

            if state == ADOPTABLE and (args.adopt or args.force):
                print(f"  adopt {name} ({why})", file=sys.stderr)
                adopted.append(name)
                owned.append(name)
                continue
            if state == ADOPTABLE:
                print(f"  SKIP  {name}: {why}; rerun with --adopt to take ownership",
                      file=sys.stderr)
                skipped.append(name)
                continue
            if state == COLLISION:
                if not args.force or why.startswith("case-clash"):
                    # A case-clash cannot be force-replaced safely: on a
                    # case-insensitive filesystem it is the same directory.
                    print(f"  SKIP  {name}: {why}", file=sys.stderr)
                    skipped.append(name)
                    continue
                if dry:
                    print(f"  would back up {name} then project ({why})", file=sys.stderr)
                else:
                    moved = backup_unmanaged(dst, label, name, stamp)
                    print(f"  backed up {name} -> {moved}", file=sys.stderr)
                forced.append(name)
                state = NEW

            if state == OWNED and is_current(dst, expected, src, args.mode):
                print(f"  ok    {name} (unchanged)", file=sys.stderr)
                owned.append(name)
                continue

            if dry:
                print(f"  would {'replace' if state == OWNED else 'project'} {name}",
                      file=sys.stderr)
                owned.append(name)
                continue

            new = stage_new(stage, name, src, body, args.mode)
            swap_in(new, dst, stage)
            print(f"  {'replaced' if state == OWNED else 'projected'} {name}", file=sys.stderr)
            owned.append(name)

            if kind == "core":
                projected = dst / "SKILL.md"
                if projected.exists():
                    digest = hashlib.sha256(projected.read_bytes()).hexdigest()
                    if digest != s["content_sha256"]:
                        failures.append(f"{name}: projected hash mismatch")
                else:
                    failures.append(f"{name}: SKILL.md missing after projection")
    finally:
        if not dry:
            shutil.rmtree(stage, ignore_errors=True)

    # Owned names no longer in the lock are stale: remove only those. A name still
    # in the lock that failed or was skipped this run is not stale -- it stays on
    # disk and stays ours, so a transient failure can never delete a skill.
    in_lock = {i[1] for i in items}
    for name in sorted(previously_owned & in_lock - set(owned)):
        if (root / name).exists() or (root / name).is_symlink():
            owned.append(name)
    stale = sorted(previously_owned - set(owned) - in_lock)
    if stale:
        remove_owned(root, stale, dry)

    if not dry:
        write_manifest(root, owned, scope, args.mode, label, manifest)

    unmanaged_after: list[str] = []
    if root.exists() and not dry:
        unmanaged_after = [p.name for p in root.iterdir()
                           if p.name != MANIFEST_NAME and p.name not in owned]
    expected_unmanaged = unmanaged_before - set(adopted) - set(forced)

    core = len(lock["skills"])
    print(f"  scope={scope} mode={args.mode}{' (dry-run)' if dry else ''}", file=sys.stderr)
    print(f"  core skills   : {core}", file=sys.stderr)
    print(f"  entrypoints   : {sum(1 for i in items if i[0] == 'entry')}", file=sys.stderr)
    print(f"  owned total   : {len(owned)}", file=sys.stderr)
    if adopted:
        print(f"  adopted       : {', '.join(adopted)}", file=sys.stderr)
    if forced:
        print(f"  backed up     : {', '.join(forced)}", file=sys.stderr)
    if skipped:
        print(f"  SKIPPED (collision): {', '.join(skipped)}", file=sys.stderr)
    if not dry:
        print(f"  unmanaged kept: {len(unmanaged_after)}"
              f"{' -> ' + ', '.join(unmanaged_after) if unmanaged_after else ''}",
              file=sys.stderr)
        if set(unmanaged_after) != expected_unmanaged:
            print("  WARNING: unmanaged skill set changed unexpectedly", file=sys.stderr)
    for f in failures:
        print(f"  FAIL {f}", file=sys.stderr)
    print(f"  failures      : {len(failures)}", file=sys.stderr)
    return failures, skipped


def prune_one(label: str, root: Path, scope: str, args) -> None:
    manifest = read_manifest(root)
    previously_owned = manifest.get("owned", [])
    unmanaged = [p.name for p in root.iterdir()
                 if p.name != MANIFEST_NAME and p.name not in previously_owned] \
        if root.exists() else []
    print(f"pruning [{label}] {root}", file=sys.stderr)
    n = remove_owned(root, previously_owned, args.dry_run)
    if not args.dry_run:
        write_manifest(root, [], scope, args.mode, label, manifest)
    print(f"removed {n}; preserved {len(unmanaged)} unmanaged", file=sys.stderr)


def run(args, repo_root: Path) -> int:
    scope = args.scope or ("user" if (args.targets or args.sync) else "project")
    targets: list[str] = []
    if args.targets:
        try:
            targets = parse_targets(args.targets)
        except ValueError as e:
            print(f"refused: {e}", file=sys.stderr)
            return 1
    elif args.sync:
        targets = ["claude", "agents"]
    if targets and scope == "project":
        print("refused: --targets are user-scope; drop --scope project", file=sys.stderr)
        return 1
    if args.adopt and args.force:
        print("refused: --adopt and --force are mutually exclusive", file=sys.stderr)
        return 1

    roots = projection_roots(scope, targets)

    if args.prune:
        for label, root in roots:
            prune_one(label, root, scope, args)
        return 0

    if args.sync:
        if args.dry_run:
            print("would: git pull --ff-only", file=sys.stderr)
        else:
            ok, msg = git_pull(repo_root)
            print(f"git pull --ff-only: {msg or 'ok'}", file=sys.stderr)
            if not ok:
                print("refused: sync aborted, pull failed. Nothing was projected.",
                      file=sys.stderr)
                return 1

    lock_path = Path(args.lock)
    lock = json.load(open(lock_path, encoding="utf-8"))
    if lock.get("status") != "locked":
        print(f"refused: lock status is '{lock.get('status')}'. "
              f"Project only from a fully locked core.", file=sys.stderr)
        return 1

    workflows = load_workflows()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    all_failures: list[str] = []
    all_skipped: list[str] = []
    for label, root in roots:
        failures, skipped = project_one(label, root, scope, args, lock, workflows, stamp)
        all_failures += failures
        all_skipped += skipped

    if all_failures:
        return 1
    if all_skipped:
        print(f"\n{len(all_skipped)} collision(s) skipped. Resolve with --adopt "
              f"(identical content) or --force (backs up first).", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=["project", "user"], default=None,
                    help="project = <repo>/.agents/skills (default); user = ~/.agents/skills")
    ap.add_argument("--targets", default=None,
                    help="comma list of user-scope targets: claude, agents")
    ap.add_argument("--mode", choices=["copy", "link"], default="copy",
                    help="copy is portable and the default; link is for development")
    ap.add_argument("--lock", default=LOCK, help="relative to the repo root")
    ap.add_argument("--root", default=None,
                    help="repo root (default: SKILLCORE_ROOT or this script's parent)")
    ap.add_argument("--sync", action="store_true",
                    help="git pull --ff-only first; defaults targets to claude,agents")
    ap.add_argument("--adopt", action="store_true",
                    help="take ownership of unmanaged dirs identical to the vendored tree")
    ap.add_argument("--force", action="store_true",
                    help="back up colliding unmanaged dirs outside the skills roots, then project")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="remove the projection and exit; unmanaged skills survive")
    args = ap.parse_args(argv)

    root = Path(args.root or os.environ.get("SKILLCORE_ROOT") or REPO_ROOT).resolve()
    prev = Path.cwd()
    os.chdir(root)  # lock, vendor_path, workflows and project scope are repo-relative
    try:
        return run(args, root)
    finally:
        os.chdir(prev)


if __name__ == "__main__":
    sys.exit(main())
