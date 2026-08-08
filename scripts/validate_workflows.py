#!/usr/bin/env python3
"""
validate_workflows.py -- Verify every workflow stage resolves against the lock.

Checks:
  1. TOML parses
  2. stage `order` values are unique and contiguous from 1
  3. every stage declares a durable `output`
  4. every referenced skill id exists in sources.lock.json
  5. candidate output paths never write into skill-core/

Exit 0 = clean, 1 = validation failures.
"""
import glob
import json
import os
import sys

try:
    import tomllib
except ImportError:  # py<3.11
    import tomli as tomllib

LOCK = "skill-core/sources.lock.json"
GAPS = "skill-core/gap_report.json"


def main() -> int:
    lock = json.load(open(LOCK))
    locked = {s["id"] for s in lock["skills"]}
    gapped = set()
    if os.path.exists(GAPS):
        g = json.load(open(GAPS))
        gapped = ({x["id"] for x in g.get("gaps", [])} |
                  {x["id"] for x in g.get("rejected", [])})

    failures, warnings = [], []
    files = sorted(glob.glob("workflows/*/workflow.toml"))
    if not files:
        print("no workflows found", file=sys.stderr)
        return 1

    for path in files:
        wf = tomllib.load(open(path, "rb"))
        wid = wf["workflow"]["id"]
        stages = wf.get("stage", [])

        orders = [s["order"] for s in stages]
        if sorted(orders) != list(range(1, len(stages) + 1)):
            failures.append(f"{wid}: stage order not contiguous from 1: {orders}")

        for s in stages:
            if not s.get("output"):
                failures.append(f"{wid}/{s['id']}: no durable output declared")
            sk = s.get("skill")
            if sk and sk not in locked:
                if sk in gapped:
                    failures.append(
                        f"{wid}/{s['id']}: skill '{sk}' is in the gap report, not locked")
                else:
                    failures.append(
                        f"{wid}/{s['id']}: skill '{sk}' is not in selection.json at all")

        for key, val in (wf.get("outputs") or {}).items():
            if str(val).startswith("skill-core"):
                failures.append(f"{wid}: outputs.{key} writes into skill-core/")

        gates = [s["id"] for s in stages if s.get("gate")]
        if not gates:
            warnings.append(f"{wid}: no approval gate declared")

        print(f"  {wid}: {len(stages)} stages, gate={gates or 'none'}", file=sys.stderr)

    for w in warnings:
        print(f"  WARN  {w}", file=sys.stderr)
    for f in failures:
        print(f"  FAIL  {f}", file=sys.stderr)

    print(f"\n{len(files)} workflow(s), {len(failures)} failure(s), "
          f"{len(warnings)} warning(s)", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
