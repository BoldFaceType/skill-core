#!/usr/bin/env python3
"""
Tests for scripts/project_skills.py -- user-scope targets, collision handling, sync.

stdlib unittest only (ADR-0005: scripts, not a framework). Every test runs in a
temp repo with HOME/USERPROFILE pointed at a temp home, so nothing touches the
real ~/.claude or ~/.agents.

    python -m unittest discover -s tests -v

Exit codes under test: 0 ok, 1 refused/failed, 2 collision skipped.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import project_skills as ps  # noqa: E402

MANIFEST = ps.MANIFEST_NAME


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def skill_md(name: str, body: str = "v1") -> str:
    return f"---\nname: {name}\ndescription: {name} test skill\n---\n# {name} {body}\n"


def make_repo(root: Path, ids=("alpha", "beta")) -> None:
    """Minimal locked core: each skill has SKILL.md plus a references/ file."""
    skills = []
    for sid in ids:
        src = root / "skill-core" / "vendor" / "up" / f"{sid}-src"
        (src / "references").mkdir(parents=True, exist_ok=True)
        text = skill_md(sid)
        (src / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
        (src / "references" / "note.md").write_text(f"note for {sid}\n", encoding="utf-8")
        skills.append({
            "id": sid,
            "vendor_path": f"skill-core/vendor/up/{sid}-src/SKILL.md",
            "content_sha256": sha(text),
        })
    write_lock(root, skills)


def write_lock(root: Path, skills: list[dict]) -> None:
    lock = root / "skill-core" / "sources.lock.json"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"schema_version": 1, "status": "locked",
                                "skills": skills}, indent=2), encoding="utf-8")


def rewrite_skill(root: Path, sid: str, body: str) -> None:
    """Change a vendored skill and keep the lock hash honest."""
    src = root / "skill-core" / "vendor" / "up" / f"{sid}-src"
    text = skill_md(sid, body)
    (src / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")
    lock_path = root / "skill-core" / "sources.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for s in lock["skills"]:
        if s["id"] == sid:
            s["content_sha256"] = sha(text)
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")


def tree(p: Path) -> dict[str, bytes]:
    return {f.relative_to(p).as_posix(): f.read_bytes()
            for f in sorted(p.rglob("*")) if f.is_file()}


def can_symlink(tmp: Path) -> bool:
    try:
        (tmp / "_l").symlink_to(tmp, target_is_directory=True)
        (tmp / "_l").unlink()
        return True
    except (OSError, NotImplementedError):
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / "repo"
        self.home = self.tmp / "home"
        self.repo.mkdir()
        self.home.mkdir()
        env = mock.patch.dict(os.environ, {"HOME": str(self.home),
                                           "USERPROFILE": str(self.home)})
        env.start()
        self.addCleanup(env.stop)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        self.claude = self.home / ".claude" / "skills"
        self.agents = self.home / ".agents" / "skills"
        make_repo(self.repo)

    def run_ps(self, *args: str) -> int:
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = ps.main(["--root", str(self.repo), *args])
        self.err = err.getvalue()
        return code

    def owned(self, root: Path) -> list[str]:
        return json.loads((root / MANIFEST).read_text(encoding="utf-8"))["owned"]

    def vendor(self, sid: str) -> Path:
        return self.repo / "skill-core" / "vendor" / "up" / f"{sid}-src"


class TestTargets(Base):
    # 1
    def test_fresh_install_both_targets(self):
        self.assertEqual(self.run_ps("--targets", "claude,agents"), 0, self.err)
        for root in (self.claude, self.agents):
            self.assertEqual(self.owned(root), ["alpha", "beta"])
            self.assertEqual(tree(root / "alpha"), tree(self.vendor("alpha")))
            self.assertEqual(tree(root / "beta"), tree(self.vendor("beta")))

    # 2
    def test_rerun_is_noop(self):
        self.assertEqual(self.run_ps("--targets", "claude,agents"), 0, self.err)
        before = {r: tree(r) for r in (self.claude, self.agents)}
        self.assertEqual(self.run_ps("--targets", "claude,agents"), 0, self.err)
        self.assertEqual(before, {r: tree(r) for r in (self.claude, self.agents)})
        self.assertFalse((self.claude.parent / ps.STAGE_NAME).exists())
        self.assertFalse((self.home / ps.BACKUP_NAME).exists())

    def test_default_targets_unchanged_is_project_scope(self):
        self.assertEqual(self.run_ps(), 0, self.err)
        self.assertTrue((self.repo / ".agents" / "skills" / "alpha" / "SKILL.md").exists())
        self.assertFalse(self.claude.exists())

    def test_bad_target_refused(self):
        self.assertEqual(self.run_ps("--targets", "claude,bogus"), 1)
        self.assertFalse(self.claude.exists())

    def test_project_scope_with_targets_refused(self):
        self.assertEqual(self.run_ps("--scope", "project", "--targets", "claude"), 1)

    def test_adopt_and_force_are_exclusive(self):
        self.assertEqual(self.run_ps("--targets", "claude", "--adopt", "--force"), 1)

    def test_stale_owned_removed_unmanaged_kept(self):
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        (self.claude / "handmade").mkdir()
        (self.claude / "handmade" / "SKILL.md").write_text("mine", encoding="utf-8")
        lock = json.loads((self.repo / "skill-core/sources.lock.json").read_text())
        lock["skills"] = [s for s in lock["skills"] if s["id"] != "beta"]
        write_lock(self.repo, lock["skills"])
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        self.assertFalse((self.claude / "beta").exists())
        self.assertEqual((self.claude / "handmade" / "SKILL.md").read_text(), "mine")
        self.assertEqual(self.owned(self.claude), ["alpha"])


class TestCollisions(Base):
    def unmanaged_alpha(self, text="mine") -> Path:
        d = self.claude / "alpha"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8")
        return d

    # 3
    def test_collision_skips_and_leaves_bytes(self):
        d = self.unmanaged_alpha()
        before = tree(d)
        self.assertEqual(self.run_ps("--targets", "claude"), 2, self.err)
        self.assertEqual(tree(d), before)
        self.assertNotIn("alpha", self.owned(self.claude))
        self.assertIn("beta", self.owned(self.claude))
        self.assertTrue((self.claude / "beta" / "SKILL.md").exists())

    # 4
    def test_adopt_identical_tree(self):
        shutil.copytree(self.vendor("alpha"), self.claude / "alpha")
        before = tree(self.claude / "alpha")
        self.assertEqual(self.run_ps("--targets", "claude"), 2, self.err)
        self.assertNotIn("alpha", self.owned(self.claude))
        self.assertEqual(self.run_ps("--targets", "claude", "--adopt"), 0, self.err)
        self.assertIn("alpha", self.owned(self.claude))
        self.assertEqual(tree(self.claude / "alpha"), before)

    # 9
    def test_same_skill_md_extra_file_is_collision_even_with_adopt(self):
        d = self.claude / "alpha"
        shutil.copytree(self.vendor("alpha"), d)
        (d / "my-extra.md").write_text("keep me", encoding="utf-8")
        before = tree(d)
        self.assertEqual(self.run_ps("--targets", "claude", "--adopt"), 2, self.err)
        self.assertEqual(tree(d), before)
        self.assertNotIn("alpha", self.owned(self.claude))

    # 5 + 8
    def test_force_backs_up_outside_every_skills_root(self):
        d = self.unmanaged_alpha("precious")
        self.assertEqual(self.run_ps("--targets", "claude,agents", "--force"), 0, self.err)
        self.assertEqual(tree(self.claude / "alpha"), tree(self.vendor("alpha")))
        backups = list((self.home / ps.BACKUP_NAME).glob("*/claude/alpha/SKILL.md"))
        self.assertEqual([b.read_text() for b in backups], ["precious"])
        # 8: no phantom skill left behind in any root, no stage dir
        self.assertEqual({p.name for p in self.claude.iterdir()},
                         {"alpha", "beta", MANIFEST})
        self.assertEqual({p.name for p in self.agents.iterdir()},
                         {"alpha", "beta", MANIFEST})
        self.assertFalse((self.claude.parent / ps.STAGE_NAME).exists())
        for root in (self.claude, self.agents):
            for b in backups:
                self.assertNotIn(root.resolve(), b.resolve().parents)
        self.assertFalse(d.with_name("alpha.bak").exists())

    # 12
    def test_case_clash_is_collision(self):
        clash = self.claude / "Alpha"
        clash.mkdir(parents=True)
        (clash / "SKILL.md").write_text("other", encoding="utf-8")
        self.assertEqual(self.run_ps("--targets", "claude"), 2, self.err)
        self.assertEqual((clash / "SKILL.md").read_text(), "other")
        self.assertNotIn("alpha", self.owned(self.claude))

    def test_unmanaged_symlink_is_collision(self):
        if not can_symlink(self.tmp):
            self.skipTest("symlinks unavailable")
        ext = self.tmp / "ext"
        ext.mkdir()
        (ext / "SKILL.md").write_text("ext", encoding="utf-8")
        self.claude.mkdir(parents=True)
        (self.claude / "alpha").symlink_to(ext, target_is_directory=True)
        self.assertEqual(self.run_ps("--targets", "claude"), 2, self.err)
        self.assertTrue((self.claude / "alpha").is_symlink())
        self.assertEqual((ext / "SKILL.md").read_text(), "ext")

    def test_dry_run_touches_nothing(self):
        d = self.unmanaged_alpha()
        before = tree(self.claude)
        self.assertEqual(self.run_ps("--targets", "claude", "--dry-run"), 2, self.err)
        self.assertEqual(tree(self.claude), before)
        self.assertTrue(d.is_dir())
        self.assertFalse((self.claude / MANIFEST).exists())
        self.assertFalse((self.claude.parent / ps.STAGE_NAME).exists())
        self.assertFalse((self.home / ps.BACKUP_NAME).exists())
        self.assertFalse((self.agents).exists())


class TestRefusals(Base):
    # 6
    def test_reserved_ids_refused(self):
        make_repo(self.repo, ids=("alpha", "synced", "anthropic-skills"))
        self.assertEqual(self.run_ps("--targets", "claude"), 1, self.err)
        self.assertFalse((self.claude / "synced").exists())
        self.assertFalse((self.claude / "anthropic-skills").exists())
        self.assertTrue((self.claude / "alpha" / "SKILL.md").exists())

    def test_casefold_duplicate_ids_refused(self):
        make_repo(self.repo, ids=("Alpha", "alpha"))
        self.assertEqual(self.run_ps("--targets", "claude"), 1, self.err)

    def test_path_traversal_id_refused(self):
        make_repo(self.repo, ids=("alpha",))
        lock = json.loads((self.repo / "skill-core/sources.lock.json").read_text())
        lock["skills"][0]["id"] = "../escape"
        write_lock(self.repo, lock["skills"])
        self.assertEqual(self.run_ps("--targets", "claude"), 1, self.err)
        self.assertFalse((self.claude.parent / "escape").exists())

    def test_unlocked_lock_refused(self):
        lock_path = self.repo / "skill-core/sources.lock.json"
        lock = json.loads(lock_path.read_text())
        lock["status"] = "draft"
        lock_path.write_text(json.dumps(lock), encoding="utf-8")
        self.assertEqual(self.run_ps("--targets", "claude"), 1)
        self.assertFalse(self.claude.exists())


class TestSwap(Base):
    # 7
    def test_symlink_failure_falls_back_to_copy(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("no privilege")):
            self.assertEqual(self.run_ps("--targets", "claude", "--mode", "link"), 0, self.err)
        self.assertTrue((self.claude / "alpha").is_dir())
        self.assertFalse((self.claude / "alpha").is_symlink())
        self.assertEqual(tree(self.claude / "alpha"), tree(self.vendor("alpha")))

    # 10a: link-mode refresh used to refuse its own symlinks (resolve() left the root)
    def test_link_mode_refresh_keeps_source_intact(self):
        if not can_symlink(self.tmp):
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.run_ps("--targets", "claude", "--mode", "link"), 0, self.err)
        self.assertTrue((self.claude / "alpha").is_symlink())
        src_before = tree(self.vendor("alpha"))
        self.assertEqual(self.run_ps("--targets", "claude", "--mode", "link"), 0, self.err)
        self.assertTrue((self.claude / "alpha").is_symlink())
        self.assertEqual(tree(self.vendor("alpha")), src_before)

    # 10b
    def test_owned_symlink_dest_unlinked_not_followed(self):
        if not can_symlink(self.tmp):
            self.skipTest("symlinks unavailable")
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        ext = self.tmp / "ext"
        ext.mkdir()
        (ext / "keep.txt").write_text("keep", encoding="utf-8")
        shutil.rmtree(self.claude / "alpha")
        (self.claude / "alpha").symlink_to(ext, target_is_directory=True)
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        self.assertFalse((self.claude / "alpha").is_symlink())
        self.assertEqual(tree(self.claude / "alpha"), tree(self.vendor("alpha")))
        self.assertEqual((ext / "keep.txt").read_text(), "keep")

    # 11
    def test_crash_before_swap_leaves_old_skill(self):
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        old = tree(self.claude / "alpha")
        rewrite_skill(self.repo, "alpha", "v2")
        with mock.patch.object(ps, "swap_in", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.run_ps("--targets", "claude")
        self.assertEqual(tree(self.claude / "alpha"), old)
        # next clean run converges and leaves no debris
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        self.assertEqual(tree(self.claude / "alpha"), tree(self.vendor("alpha")))
        self.assertFalse((self.claude.parent / ps.STAGE_NAME).exists())

    def test_failed_second_rename_restores_old(self):
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        old = tree(self.claude / "alpha")
        rewrite_skill(self.repo, "alpha", "v2")
        real = os.replace
        calls = {"n": 0}

        def flaky(a, b):
            calls["n"] += 1
            if Path(b) == self.claude / "alpha" and calls["n"] > 1 and "new" in Path(a).parts:
                raise OSError("disk full")
            return real(a, b)

        with mock.patch.object(ps.os, "replace", side_effect=flaky):
            with self.assertRaises(OSError):
                self.run_ps("--targets", "claude")
        self.assertEqual(tree(self.claude / "alpha"), old)

    def test_failed_item_still_in_lock_is_not_swept_as_stale(self):
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        before = tree(self.claude / "alpha")
        shutil.rmtree(self.vendor("alpha"))  # lock still lists alpha; vendor dir gone
        self.assertEqual(self.run_ps("--targets", "claude"), 1, self.err)
        self.assertEqual(tree(self.claude / "alpha"), before)  # not deleted
        self.assertIn("alpha", self.owned(self.claude))        # still ours

    def test_entrypoint_workflow_projected_as_lf_bytes(self):
        wf = self.repo / "workflows" / "demo"
        wf.mkdir(parents=True)
        (wf / "workflow.toml").write_text(
            '[workflow]\nid = "demo"\ntitle = "Demo"\ndescription = "d"\n'
            '[[stage]]\nid = "s1"\norder = 1\nskill = "alpha"\noutput = "o.md"\n',
            encoding="utf-8")
        if sys.version_info < (3, 11):
            self.skipTest("tomllib needs 3.11")
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        body = (self.claude / "workflow-demo" / "SKILL.md").read_bytes()
        self.assertNotIn(b"\r\n", body)
        self.assertIn("workflow-demo", self.owned(self.claude))
        # unchanged second run is a no-op
        self.assertEqual(self.run_ps("--targets", "claude"), 0, self.err)
        self.assertEqual((self.claude / "workflow-demo" / "SKILL.md").read_bytes(), body)


class TestSync(Base):
    def test_pull_failure_aborts_before_projecting(self):
        with mock.patch.object(ps, "git_pull", return_value=(False, "diverged")):
            self.assertEqual(self.run_ps("--sync"), 1)
        self.assertFalse(self.claude.exists())
        self.assertFalse(self.agents.exists())

    def test_sync_defaults_to_both_user_targets(self):
        with mock.patch.object(ps, "git_pull", return_value=(True, "Already up to date.")) as gp:
            self.assertEqual(self.run_ps("--sync"), 0, self.err)
        gp.assert_called_once()
        for root in (self.claude, self.agents):
            self.assertEqual(self.owned(root), ["alpha", "beta"])

    def test_sync_dry_run_does_not_pull(self):
        with mock.patch.object(ps, "git_pull") as gp:
            self.assertEqual(self.run_ps("--sync", "--dry-run"), 0, self.err)
        gp.assert_not_called()
        self.assertFalse(self.claude.exists())

    def test_root_independent_of_cwd(self):
        os.chdir(self.tmp)
        self.assertEqual(self.run_ps("--targets", "agents"), 0, self.err)
        self.assertTrue((self.agents / "alpha" / "SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
