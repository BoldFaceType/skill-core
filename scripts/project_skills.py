#!/usr/bin/env python3
"""
project_skills.py -- Materialize the shared Agent Skills projection.

Copies vendored Skill Core skills into `.agents/skills/` so Codex, OpenCode, and
GitHub agents discover the same tree, and generates one entrypoint skill per
workflow.

Ownership is explicit. The projection manifest `.skillstore-projection.json`
records every path this script created. On refresh, only those paths are
removed. A skill installed by hand -- or by any other tool -- is never touched.
There is no CLI framework here on purpose: the projection is a file copy, and a
package with subcommands would be machinery the task does not need.

Usage:
    python scripts/project_skills.py                      # project scope, copy
    python scripts/project_skills.py --scope user         # ~/.agents/skills
    python scripts/project_skills.py --mode link          # symlink (dev)
    python scripts/project_skills.py --dry-run            # report only
    python scripts/project_skills.py --prune              # remove projection

Exit 0 = projection matches the lock, 1 = refused or failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import date, timezone, datetime
from pathlib import Path

LOCK = "skill-core/sources.lock.json"
WORKFLOWS = "workflows"
MANIFEST_NAME = ".skillstore-projection.json"


def projection_root(scope: str) -> Path:
    """Project scope lives in the repo; user scope in the home directory."""
    if scope == "user":
        return Path.home() / ".agents" / "skills"
    return Path(".agents") / "skills"


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


def write_manifest(root: Path, owned: list[str], scope: str, mode: str) -> None:
    payload = {
        "schema_version": 1,
        "generator": "scripts/project_skills.py",
        "generated": date.today().isoformat(),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": scope,
        "mode": mode,
        "owned": sorted(owned),
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / MANIFEST_NAME).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def remove_owned(root: Path, owned: list[str], dry: bool) -> int:
    """
    Remove only paths this script previously created.

    Anything not listed in the manifest survives, which is what makes it safe to
    run against a directory the user also installs skills into by hand.
    """
    removed = 0
    for rel in owned:
        target = root / rel
        # Refuse to act outside the projection root, whatever the manifest says.
        try:
            target.resolve().relative_to(root.resolve())
        except ValueError:
            print(f"  refused (outside root): {rel}", file=sys.stderr)
            continue
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


def link_or_copy(src: Path, dst: Path, mode: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if mode == "link":
        try:
            dst.symlink_to(src.resolve(), target_is_directory=True)
            return
        except OSError:
            # Windows without Developer Mode cannot symlink unprivileged.
            print(f"  symlink unavailable, copying: {dst.name}", file=sys.stderr)
    shutil.copytree(src, dst)


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


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scope", choices=["project", "user"], default="project")
    ap.add_argument("--mode", choices=["copy", "link"], default="copy",
                    help="copy is portable and the default; link is for development")
    ap.add_argument("--lock", default=LOCK)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="remove the projection and exit; unmanaged skills survive")
    args = ap.parse_args()

    root = projection_root(args.scope)
    manifest = read_manifest(root)
    previously_owned = manifest.get("owned", [])

    # Count what we do not own, so the preservation guarantee is observable.
    unmanaged_before = []
    if root.exists():
        unmanaged_before = [p.name for p in root.iterdir()
                            if p.name != MANIFEST_NAME and p.name not in previously_owned]

    if args.prune:
        print(f"pruning projection at {root}", file=sys.stderr)
        n = remove_owned(root, previously_owned, args.dry_run)
        if not args.dry_run:
            write_manifest(root, [], args.scope, args.mode)
        print(f"removed {n}; preserved {len(unmanaged_before)} unmanaged",
              file=sys.stderr)
        return 0

    lock = json.load(open(args.lock, encoding="utf-8"))
    if lock.get("status") != "locked":
        print(f"refused: lock status is '{lock.get('status')}'. "
              f"Project only from a fully locked core.", file=sys.stderr)
        return 1

    # Refresh: clear what we own, then rebuild. Never a blanket delete.
    remove_owned(root, previously_owned, args.dry_run)

    owned: list[str] = []
    failures: list[str] = []

    for s in lock["skills"]:
        src = Path(s["vendor_path"]).parent
        if not src.is_dir():
            failures.append(f"{s['id']}: vendor dir missing at {src}")
            continue
        dst = root / s["id"]
        if args.dry_run:
            print(f"  would project {s['id']:<28} <- {src}", file=sys.stderr)
        else:
            link_or_copy(src, dst, args.mode)
            # Verify the projected SKILL.md against the lock, same as vendoring.
            projected = dst / "SKILL.md"
            if projected.exists():
                digest = hashlib.sha256(projected.read_bytes()).hexdigest()
                if digest != s["content_sha256"]:
                    failures.append(f"{s['id']}: projected hash mismatch")
            else:
                failures.append(f"{s['id']}: SKILL.md missing after projection")
        owned.append(s["id"])

    for wf in load_workflows():
        name = f"workflow-{wf['workflow']['id']}"
        dst = root / name / "SKILL.md"
        if args.dry_run:
            print(f"  would generate {name}", file=sys.stderr)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(entrypoint_body(wf), encoding="utf-8")
        owned.append(name)

    if not args.dry_run:
        write_manifest(root, owned, args.scope, args.mode)

    unmanaged_after = []
    if root.exists() and not args.dry_run:
        unmanaged_after = [p.name for p in root.iterdir()
                           if p.name != MANIFEST_NAME and p.name not in owned]

    for f in failures:
        print(f"  FAIL {f}", file=sys.stderr)

    core = len(lock["skills"])
    print(f"\nprojection: {root}", file=sys.stderr)
    print(f"  scope={args.scope} mode={args.mode}"
          f"{' (dry-run)' if args.dry_run else ''}", file=sys.stderr)
    print(f"  core skills   : {core}", file=sys.stderr)
    print(f"  entrypoints   : {len(owned) - core}", file=sys.stderr)
    print(f"  owned total   : {len(owned)}", file=sys.stderr)
    if not args.dry_run:
        print(f"  unmanaged kept: {len(unmanaged_after)}"
              f"{' -> ' + ', '.join(unmanaged_after) if unmanaged_after else ''}",
              file=sys.stderr)
        if len(unmanaged_after) != len(unmanaged_before):
            print("  WARNING: unmanaged skill count changed", file=sys.stderr)
    print(f"  failures      : {len(failures)}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
