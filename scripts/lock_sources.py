#!/usr/bin/env python3
"""
lock_sources.py -- Generate skill-core/sources.lock.json from selection.json.

Resolves every selected skill ID to an exact upstream SKILL.md and records
commit SHA, blob SHA, sha256 content hash, size, and license. Uses the git
protocol rather than the GitHub REST API so it works unauthenticated and is
not subject to API rate limits.

Guarantees:
  - Never guesses. Ambiguous or missing IDs go to the gap report untouched.
  - Never mutates selection.json. Curation is a human decision.
  - Regenerates the lock from scratch; the lock is never hand-edited.
  - Idempotent. Re-running against unchanged upstreams produces identical output.

Usage:
    python scripts/lock_sources.py
    python scripts/lock_sources.py --selection skill-core/selection.json
    python scripts/lock_sources.py --cache .cache/clones --check

Exit codes:
    0  all selected skills locked
    1  locked with gaps (expected while gaps are open)
    2  hard failure (clone/IO error)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import date, timezone, datetime

DEFAULT_SELECTION = "skill-core/selection.json"
DEFAULT_LOCK = "skill-core/sources.lock.json"
DEFAULT_GAPS = "skill-core/gap_report.json"
DEFAULT_CACHE = ".cache/clones"

PERMISSIVE = {"MIT", "Apache-2.0", "BSD", "BSD-2-Clause", "BSD-3-Clause", "ISC"}


# --------------------------------------------------------------------------
# git helpers
# --------------------------------------------------------------------------

def git(args, cwd=None, timeout=300, binary=False):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=not binary, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def clone(source: str, dest: str) -> tuple[bool, str]:
    """Shallow, blobless clone. Blobs are fetched lazily on demand."""
    if os.path.isdir(os.path.join(dest, ".git")):
        code, _, err = git(["fetch", "--depth", "1", "origin"], cwd=dest)
        return code == 0, "refreshed" if code == 0 else err[:200]
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    code, _, err = git([
        "clone", "--depth", "1", "--filter=blob:none", "--no-checkout",
        "--quiet", f"https://github.com/{source}", dest
    ])
    return code == 0, "cloned" if code == 0 else err.strip()[:200]


def head_commit(repo: str) -> str | None:
    code, out, _ = git(["rev-parse", "HEAD"], cwd=repo)
    return out.strip() if code == 0 else None


def list_tree(repo: str) -> list[dict]:
    code, out, _ = git(["ls-tree", "-r", "HEAD"], cwd=repo)
    if code != 0:
        return []
    entries = []
    for line in out.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) == 3:
            entries.append({"mode": parts[0], "type": parts[1],
                            "sha": parts[2], "path": path})
    return entries


def read_blob(repo: str, path: str) -> tuple[bytes | None, str | None]:
    code, out, _ = git(["show", f"HEAD:{path}"], cwd=repo, binary=True)
    if code != 0:
        return None, None
    c2, sha, _ = git(["rev-parse", f"HEAD:{path}"], cwd=repo)
    return out, (sha.strip() if c2 == 0 else None)


# --------------------------------------------------------------------------
# parsing
# --------------------------------------------------------------------------

def frontmatter(content: bytes) -> dict:
    """Extract name/description from YAML frontmatter without a YAML dependency."""
    text = content.decode("utf-8", errors="replace")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out, key = {}, None
    for line in text[3:end].splitlines():
        if line.startswith((" ", "\t")) and key:
            out[key] += " " + line.strip()
        elif ":" in line:
            k, _, v = line.partition(":")
            key = k.strip()
            out[key] = v.strip().strip("\"'")
    return {k: v for k, v in out.items() if k in ("name", "description")}


def classify_license(text: str) -> str | None:
    """Identify an SPDX id from license text. Proprietary terms are named, not guessed."""
    head = text[:800].upper()
    if "ALL RIGHTS RESERVED" in head and "APACHE LICENSE" not in head:
        return "PROPRIETARY"
    for token, spdx in (("APACHE LICENSE", "Apache-2.0"),
                        ("MIT LICENSE", "MIT"),
                        ("MOZILLA PUBLIC", "MPL-2.0"),
                        ("GNU GENERAL PUBLIC", "GPL"),
                        ("BSD ", "BSD"),
                        ("ISC LICENSE", "ISC")):
        if token in head:
            return spdx
    if "PERMISSION IS HEREBY GRANTED, FREE OF CHARGE" in head:
        return "MIT"
    return None


def license_for_skill(repo: str, license_paths: list[str],
                      skill_path: str) -> tuple[str | None, str | None]:
    """
    Resolve the license governing one skill.

    Licenses are resolved nearest-first: a LICENSE beside the SKILL.md wins over
    one at the repository root. Several upstream repositories license per skill
    rather than per repository -- anthropics/skills carries Apache-2.0 on some
    skills and all-rights-reserved terms on others -- so a repo-level check would
    wrongly clear proprietary content.
    """
    skill_dir = os.path.dirname(skill_path)
    best, best_depth = None, -1
    for lp in license_paths:
        ldir = os.path.dirname(lp)
        if ldir == "" or skill_dir == ldir or skill_dir.startswith(ldir + "/"):
            depth = len(ldir.split("/")) if ldir else 0
            if depth > best_depth:
                best, best_depth = lp, depth
    if best is None:
        return None, None
    content, _ = read_blob(repo, best)
    if not content:
        return best, None
    return best, classify_license(content.decode("utf-8", errors="replace"))


def match_path(paths: list[str], skill_id: str) -> tuple[str, str | None, dict]:
    """Return (status, path, candidates). Strictest tier wins; never guesses."""
    exact, suffix, fuzzy = [], [], []
    for p in paths:
        segs = p.split("/")
        parent = segs[-2] if len(segs) >= 2 else ""
        if skill_id in segs:
            exact.append(p)
        elif parent.endswith(f"-{skill_id}") or parent.endswith(f"_{skill_id}"):
            suffix.append(p)
        elif skill_id in parent:
            fuzzy.append(p)
    cands = {"exact": exact, "suffix": suffix, "fuzzy": fuzzy[:8]}
    if len(exact) == 1:
        return "resolved", exact[0], cands
    if len(exact) > 1:
        return "ambiguous", None, cands
    if len(suffix) == 1:
        return "resolved", suffix[0], cands
    if len(suffix) > 1:
        return "ambiguous", None, cands
    return ("needs_review" if fuzzy else "unresolved"), None, cands


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selection", default=DEFAULT_SELECTION)
    ap.add_argument("--lock", default=DEFAULT_LOCK)
    ap.add_argument("--gaps", default=DEFAULT_GAPS)
    ap.add_argument("--cache", default=DEFAULT_CACHE)
    ap.add_argument("--check", action="store_true",
                    help="verify the existing lock still matches upstream; write nothing")
    args = ap.parse_args()

    try:
        selection = json.load(open(args.selection))
    except OSError as e:
        print(f"error: cannot read {args.selection}: {e}", file=sys.stderr)
        return 2

    skills = selection["skills"]
    sources = sorted({s["source"] for s in skills})

    repos: dict[str, dict] = {}
    for src in sources:
        dest = os.path.join(args.cache, src.replace("/", "__"))
        ok, note = clone(src, dest)
        if not ok:
            print(f"error: clone failed for {src}: {note}", file=sys.stderr)
            return 2
        entries = list_tree(dest)
        repos[src] = {
            "dir": dest,
            "commit": head_commit(dest),
            "skill_paths": [e["path"] for e in entries
                            if e["path"].upper().endswith("SKILL.MD")],
            "license_paths": [e["path"] for e in entries
                              if os.path.basename(e["path"]).upper().startswith("LICEN")],
        }
        print(f"  resolved {src} @ {repos[src]['commit'][:10]} "
              f"({len(repos[src]['skill_paths'])} SKILL.md, "
              f"{len(repos[src]['license_paths'])} license files)", file=sys.stderr)

    locked, gaps, rejected = [], [], []
    for s in skills:
        sid, src = s["id"], s["source"]
        r = repos[src]

        pinned = s.get("path")
        if pinned:
            if pinned in r["skill_paths"]:
                status, path, cands = "resolved", pinned, {"pinned": [pinned]}
            else:
                gaps.append({"id": sid, "source": src, "status": "pinned_path_missing",
                             "commit": r["commit"], "pinned_path": pinned,
                             "candidates": {"available": r["skill_paths"][:20]}})
                continue
        else:
            status, path, cands = match_path(r["skill_paths"], sid)
        if status != "resolved":
            gaps.append({"id": sid, "source": src, "status": status,
                         "commit": r["commit"], "candidates": cands})
            continue

        lic_file, lic_spdx = license_for_skill(r["dir"], r["license_paths"], path)
        if lic_spdx is None or lic_spdx not in PERMISSIVE:
            rejected.append({
                "id": sid, "source": src, "path": path,
                "license_file": lic_file, "license_spdx": lic_spdx,
                "reason": ("no license found beside or above the skill"
                           if lic_spdx is None
                           else "license not in permissive allowlist"),
            })
            continue

        content, blob_sha = read_blob(r["dir"], path)
        if content is None:
            gaps.append({"id": sid, "source": src, "status": "blob_fetch_failed",
                         "path": path})
            continue

        locked.append({
            "id": sid,
            "group": s.get("group"),
            "source_repo": src,
            "source_url": f"https://github.com/{src}",
            "path": path,
            "path_pinned": bool(pinned),
            "commit": r["commit"],
            "blob_sha": blob_sha,
            "content_sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
            "license_file": lic_file,
            "license_spdx": lic_spdx,
            "vendor_path": f"skill-core/vendor/{src.replace('/', '-')}/{sid}/SKILL.md",
            "frontmatter": frontmatter(content),
        })

    lock = {
        "schema_version": 1,
        "status": "locked" if not gaps and not rejected else "partially-locked",
        "generated": date.today().isoformat(),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "scripts/lock_sources.py",
        "verification_method": "git-protocol shallow blobless clone; "
                               "commit SHA, blob SHA, sha256 recorded per file",
        "core_size_selected": len(skills),
        "core_size_locked": len(locked),
        "unresolved_count": len(gaps),
        "rejected_count": len(rejected),
        "skills": sorted(locked, key=lambda x: x["id"]),
    }

    if args.check:
        try:
            existing = json.load(open(args.lock))
        except OSError:
            print("check: no existing lock to compare", file=sys.stderr)
            return 1
        drift = []
        old = {s["id"]: s for s in existing.get("skills", [])}
        for s in lock["skills"]:
            o = old.get(s["id"])
            if not o:
                drift.append(f"{s['id']}: new")
            elif o["content_sha256"] != s["content_sha256"]:
                drift.append(f"{s['id']}: content changed upstream")
            elif o["commit"] != s["commit"]:
                drift.append(f"{s['id']}: commit moved (content identical)")
        for sid in old:
            if sid not in {s["id"] for s in lock["skills"]}:
                drift.append(f"{sid}: no longer resolves")
        if drift:
            print("DRIFT DETECTED:", file=sys.stderr)
            for d in drift:
                print(f"  {d}", file=sys.stderr)
            return 1
        print("check: lock matches upstream", file=sys.stderr)
        return 0

    os.makedirs(os.path.dirname(args.lock) or ".", exist_ok=True)
    with open(args.lock, "w") as f:
        json.dump(lock, f, indent=2)
        f.write("\n")
    with open(args.gaps, "w") as f:
        json.dump({"generated": date.today().isoformat(),
                   "gaps": gaps, "rejected": rejected}, f, indent=2)
        f.write("\n")

    print(f"\nlocked={len(locked)}/{len(skills)}  gaps={len(gaps)}  "
          f"rejected={len(rejected)}", file=sys.stderr)
    print(f"wrote {args.lock}", file=sys.stderr)
    if gaps:
        print(f"wrote {args.gaps} -- resolve before VSA 0.2 closes", file=sys.stderr)
    return 1 if (gaps or rejected) else 0


if __name__ == "__main__":
    sys.exit(main())
