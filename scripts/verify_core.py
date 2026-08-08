#!/usr/bin/env python3
"""
verify_core.py -- Assert FR1 for every skill in the core.

FR1 (PRD v0.2.0): every skill in the core is SELECTED, LOCKED, LICENSED, and
VENDORED. No skill is installable unless all four hold. The core has no target
size -- size is an outcome of curation, so this script never asserts a count.

Fully offline. No network, no clone. Suitable as the primary CI gate.

Usage:
    python scripts/verify_core.py [--json]

Exit 0 = FR1 holds for every core skill, 1 = one or more violations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

SELECTION = "skill-core/selection.json"
LOCK = "skill-core/sources.lock.json"

PERMISSIVE = {"MIT", "Apache-2.0", "BSD", "BSD-2-Clause", "BSD-3-Clause", "ISC"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selection", default=SELECTION)
    ap.add_argument("--lock", default=LOCK)
    ap.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = ap.parse_args()

    try:
        selection = json.load(open(args.selection))
        lock = json.load(open(args.lock))
    except OSError as e:
        print(f"FAIL cannot read core manifests: {e}", file=sys.stderr)
        return 1

    selected = {s["id"] for s in selection["skills"]}
    locked = {s["id"]: s for s in lock["skills"]}
    violations: list[str] = []
    rows = []

    # Lock-level state must be clean before per-skill checks mean anything.
    if lock.get("status") != "locked":
        violations.append(f"lock status is '{lock.get('status')}', expected 'locked'")
    if lock.get("unresolved_count"):
        violations.append(f"{lock['unresolved_count']} unresolved skill(s) in lock")
    if lock.get("rejected_count"):
        violations.append(f"{lock['rejected_count']} rejected skill(s) in lock")

    # Every selected skill must be locked.
    for sid in sorted(selected - set(locked)):
        violations.append(f"{sid}: SELECTED but not LOCKED")

    # Every locked skill must be selected -- a lock entry with no selection
    # means the core drifted from its curation source.
    for sid in sorted(set(locked) - selected):
        violations.append(f"{sid}: LOCKED but not SELECTED")

    for sid in sorted(locked):
        s = locked[sid]
        checks = {"selected": sid in selected, "locked": False,
                  "licensed": False, "vendored": False}

        # LOCKED: provenance fields present and non-empty.
        missing = [f for f in ("source_repo", "path", "commit", "blob_sha",
                               "content_sha256") if not s.get(f)]
        if missing:
            violations.append(f"{sid}: LOCKED incomplete -- missing {', '.join(missing)}")
        else:
            checks["locked"] = True

        # LICENSED: permissive SPDX recorded.
        spdx = s.get("license_spdx")
        if spdx not in PERMISSIVE:
            violations.append(f"{sid}: NOT LICENSED -- spdx={spdx!r}")
        else:
            checks["licensed"] = True

        # VENDORED: file on disk, hash matches the lock.
        vp = s.get("vendor_path")
        if not vp or not os.path.exists(vp):
            violations.append(f"{sid}: NOT VENDORED -- missing {vp}")
        else:
            actual = hashlib.sha256(open(vp, "rb").read()).hexdigest()
            if actual != s["content_sha256"]:
                violations.append(
                    f"{sid}: VENDOR HASH MISMATCH\n"
                    f"        lock: {s['content_sha256']}\n"
                    f"        disk: {actual}")
            else:
                checks["vendored"] = True

        rows.append({"id": sid, "license": spdx, **checks,
                     "fr1": all(checks.values())})

    passing = sum(1 for r in rows if r["fr1"])

    if args.json:
        print(json.dumps({
            "requirement": "FR1",
            "core_size": len(rows),
            "passing": passing,
            "violations": violations,
            "skills": rows,
        }, indent=2))
    else:
        print(f"{'SKILL':<30} {'SEL':<5} {'LOCK':<5} {'LIC':<5} {'VEND':<5} LICENSE",
              file=sys.stderr)
        print("-" * 72, file=sys.stderr)
        for r in rows:
            m = lambda b: " ok " if b else "FAIL"  # noqa: E731
            print(f"{r['id']:<30} {m(r['selected']):<5} {m(r['locked']):<5} "
                  f"{m(r['licensed']):<5} {m(r['vendored']):<5} {r['license']}",
                  file=sys.stderr)
        print("-" * 72, file=sys.stderr)
        for v in violations:
            print(f"  VIOLATION {v}", file=sys.stderr)
        print(f"\nFR1: {passing}/{len(rows)} skills selected + locked + "
              f"licensed + vendored", file=sys.stderr)
        if not violations:
            print("FR1 holds. Core size is an outcome, not a target -- "
                  "no count is asserted.", file=sys.stderr)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
