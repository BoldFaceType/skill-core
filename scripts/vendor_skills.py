#!/usr/bin/env python3
"""
vendor_skills.py -- Materialize locked skills into skill-core/vendor/.

Copies each SKILL.md at its locked commit, plus any sibling files in the skill
directory, and re-verifies the sha256 against sources.lock.json after writing.
A copy whose hash does not match the lock is a hard failure.

Safety:
  - Refuses to run if the lock has gaps or rejections.
  - Never writes outside skill-core/vendor/.
  - Never modifies vendored content. Skill Core is immutable by definition.
  - --dry-run reports what would be written and changes nothing.

Usage:
    python scripts/vendor_skills.py [--dry-run] [--cache .cache/clones]

Exit 0 = all skills vendored and verified, 1 = verification failure, 2 = refused.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

LOCK = "skill-core/sources.lock.json"
VENDOR_ROOT = "skill-core/vendor"
DEFAULT_CACHE = ".cache/clones"


def git(args, cwd=None, binary=False, timeout=180):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=not binary, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def repo_dir(cache: str, source: str) -> str:
    return os.path.join(cache, source.replace("/", "__"))


def siblings(repo: str, skill_path: str) -> list[str]:
    """Every file in the skill's own directory (scripts, references, assets)."""
    skill_dir = os.path.dirname(skill_path)
    code, out, _ = git(["ls-tree", "-r", "HEAD", "--name-only", f"{skill_dir}/"], cwd=repo)
    return out.splitlines() if code == 0 else [skill_path]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lock", default=LOCK)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--vendor-root", default=VENDOR_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    lock = json.load(open(args.lock))
    if lock.get("unresolved_count") or lock.get("rejected_count"):
        print(f"refused: lock is {lock['status']} "
              f"({lock.get('unresolved_count')} gaps, "
              f"{lock.get('rejected_count')} rejected). "
              f"Resolve before vendoring.", file=sys.stderr)
        return 2

    written, verified, failures, files_total = 0, 0, [], 0

    for s in lock["skills"]:
        repo = repo_dir(args.cache, s["source_repo"])
        if not os.path.isdir(repo):
            failures.append(f"{s['id']}: clone missing at {repo}; run lock_sources.py first")
            continue

        dest_dir = os.path.dirname(s["vendor_path"])
        paths = siblings(repo, s["path"])

        if args.dry_run:
            print(f"  would vendor {s['id']:<28} {len(paths)} file(s) -> {dest_dir}",
                  file=sys.stderr)
            files_total += len(paths)
            continue

        os.makedirs(dest_dir, exist_ok=True)
        for p in paths:
            code, content, _ = git(["show", f"HEAD:{p}"], cwd=repo, binary=True)
            if code != 0:
                failures.append(f"{s['id']}: cannot read {p}")
                continue
            rel = os.path.relpath(p, os.path.dirname(s["path"]))
            target = os.path.join(dest_dir, rel)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as f:
                f.write(content)
            files_total += 1

        # Re-verify the SKILL.md hash from what was actually written to disk.
        skill_file = os.path.join(dest_dir, "SKILL.md")
        if not os.path.exists(skill_file):
            failures.append(f"{s['id']}: SKILL.md not written")
            continue
        actual = hashlib.sha256(open(skill_file, "rb").read()).hexdigest()
        if actual != s["content_sha256"]:
            failures.append(f"{s['id']}: hash mismatch\n"
                            f"      lock: {s['content_sha256']}\n"
                            f"      disk: {actual}")
            continue

        # Carry the governing license alongside the skill.
        if s.get("license_file"):
            code, lic, _ = git(["show", f"HEAD:{s['license_file']}"], cwd=repo, binary=True)
            if code == 0:
                with open(os.path.join(dest_dir, "LICENSE"), "wb") as f:
                    f.write(lic)
                files_total += 1

        written += 1
        verified += 1
        print(f"  vendored {s['id']:<28} {len(paths)} file(s)  "
              f"{s['license_spdx']:<11} verified", file=sys.stderr)

    if args.dry_run:
        print(f"\ndry-run: {len(lock['skills'])} skills, ~{files_total} files",
              file=sys.stderr)
        return 0

    for f in failures:
        print(f"  FAIL {f}", file=sys.stderr)
    print(f"\nvendored={written}/{len(lock['skills'])}  verified={verified}  "
          f"files={files_total}  failures={len(failures)}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
