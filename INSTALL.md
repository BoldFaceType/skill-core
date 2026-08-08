# Install — `C:\Dev\projects\skill-core`

**Target repo:** `C:\Dev\projects\skill-core` (renamed from `Skill Core` — see warning below)
**Bundle:** `skill-core-vsa02-2026-08-08.tar.gz`
**Effect:** additive. Existing files are preserved; superseded documents are retained beside their replacements.

---

## ⚠ Read first: the path contains a space

Your own `ARCHITECTURE.md` rejected this, and the reasoning still holds:

> A literal directory name containing a space was rejected because it adds shell quoting, URI, archive, and Windows automation failure modes without adding useful state.

That decision was about the `skill-core/` directory *inside* the repo, but the same failure modes apply to the repository root — arguably more, since every CI path, every `cd`, and every agent-invoked command crosses it.

Concretely, `C:\Dev\projects\Skill Core` will bite on:

- Unquoted `cd` in any generated script or agent command
- `python -m` invocations from a working directory the caller didn't quote
- Git remotes, file URIs, and `file://` links
- Windows scheduled tasks and cron-equivalent automation
- Tar/zip round-trips where a tool splits on whitespace

**Recommended:** rename the repository root to `C:\Dev\projects\skill-core` and keep **Skill Core** as the human-facing display name — exactly the split your architecture doc already specifies for the inner directory.

```powershell
Rename-Item "C:\Dev\projects\Skill Core" "skill-core"
```

Everything below works either way; commands are quoted defensively. But the rename costs one command now and removes a permanent class of bug.

---

## 1. Prerequisites

**Python 3.11+ via `uv`** — zero global installs, per the workspace rule.

```powershell
irm https://astral.sh/uv/install.ps1 | iex   # if uv is not present
uv python install 3.12
```

Then disable the Windows App Execution Aliases for `python.exe` and `python3.exe`
(Settings -> Apps -> Advanced app settings -> App execution aliases). Left on, they
intercept `python` and print a Microsoft Store prompt instead of running anything.

All four scripts in this bundle are **stdlib-only** -- no dependencies to install.
`validate_workflows.py` needs `tomllib`, which is 3.11+ stdlib.

## 2. Unpack

Confirm both paths first. This catches the two most common failures before they cascade:

```powershell
Test-Path "C:\Dev\projects\skill-core"                                    # True
Test-Path "$env:USERPROFILE\Downloads\skill-core-vsa02-2026-08-08.tar.gz"  # True
```

If the directory was renamed per the warning above, the path is `skill-core`,
**not** `Skill Core`. If the tarball landed elsewhere, substitute its real path.

```powershell
cd "C:\Dev\projects\skill-core"
tar -xzf "$env:USERPROFILE\Downloads\skill-core-vsa02-2026-08-08.tar.gz" -C "$env:TEMP"
Copy-Item "$env:TEMP\skill-core-vsa02\*" . -Recurse -Force
Remove-Item "$env:TEMP\skill-core-vsa02" -Recurse -Force
```

`-Force` overwrites same-named files only. Nothing is deleted. `sources.lock.json` and `skill-core/vendor/` were previously absent; `selection.json` is replaced by the amended version, which records the prior state under `supersedes` and `amendments_applied`.

---

## 3. Merge the changelog

`CHANGELOG_ENTRY.md` is a fragment, not a replacement. Paste its `## [0.2.0]` block above the existing `## [0.1.0]` entry in `CHANGELOG.md`, then delete the fragment.

---

## 4. Verify

```powershell
uv run --python 3.12 scripts\verify_core.py          # exit 0 = FR1 holds for all 23
uv run --python 3.12 scripts\validate_workflows.py   # exit 0 = 0 failures, 0 warnings
uv run --python 3.12 scripts\lock_sources.py --check # exit 0 = no upstream drift
```

All three must exit 0. `verify_core.py` is the FR1 gate: it asserts every core skill is selected, locked, licensed, and vendored, and re-hashes every vendored file against the lock.

**Note on `--check`:** it re-clones upstream into `.cache/clones/` (~180 MB, gitignored). First run takes a few minutes; later runs fetch shallowly.

---

## 5. Regenerating (only if `selection.json` changes)

```powershell
uv run --python 3.12 scripts\lock_sources.py       # regenerate the lock
uv run --python 3.12 scripts\vendor_skills.py      # re-materialize + verify vendor/
uv run --python 3.12 scripts\validate_workflows.py
```

`vendor_skills.py` refuses to run against a lock with gaps or rejections. `--dry-run` reports without writing.

---

## 6. Documents to review

| File | Action |
|---|---|
| `docs/PRD.md` | **v0.2.0** — FR1 restated as a property. Supersedes v0.1.0; keep both. |
| `decisions/0004-fr1-property-not-count.md` | The amendment record |
| `skill-core/GAP_REPORT_v3_RESOLVED.md` | Final state of the six decisions |
| `docs/GLOSSARY.md` | Fixes "SkillStore v3" vs "SkillStore v1.x" ambiguity |
| `docs/DOD_POLICY.md` | No `[x]` without a verifying test |
| `.github/workflows/verify.yml` | CI gate — enable when the remote exists |

---

## 7. Push

The repository still exists in one location. Create the remote and push:

```powershell
git add -A
git commit -m "VSA 0.2: source lock, license verification, vendoring (23/23)"
git remote add origin https://github.com/BoldFaceType/skill-core.git
git push -u origin main
```

Creating the GitHub repository and authenticating are yours to do — I can't and shouldn't.

---

## Gitignore additions

```gitignore
.cache/clones/
runs/
candidates/
```

`vendor/` **is committed** — that is the point of vendoring. `.cache/clones/` is a scratch working copy and is not.
