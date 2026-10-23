"""A tree ships PORTABLE — no machine's path in any file — and is LOCALIZED at install.

Portable breadcrumbs are relative to each node's folder; the manifest stores `skill_src`
relative to itself. A portable tree validates wherever it is copied, with no step at all;
`localize=True` (materialize / emit) writes absolute breadcrumbs for one machine, and
projecting a tree (an install read through symlinks) localizes it.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from skilltree import SkillTree, TreeNode, materialize, validate
from skilltree.cohere import emit, relink
from skilltree.forest import project
from skilltree.materialize import node_skill_md


def _src(tmp_path: Path, name: str) -> Path:
    d = tmp_path / "src" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: the {name} skill\n---\n\nbody of {name}\n")
    return d


def _tree(tmp_path: Path) -> SkillTree:
    return SkillTree(TreeNode("root", "sc", description="the root", children=[
        TreeNode("a", "cor", description="branch a", children=[
            TreeNode("a1", "ac", skill_src=str(_src(tmp_path, "a1")))]),
        TreeNode("b", "skill", skill_src=str(_src(tmp_path, "b")))]))


def _all_text(root: Path) -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in root.rglob("*")
                     if p.is_file() and p.suffix in (".md", ".json"))


def _errors(root: Path) -> list:
    return [v for v in validate(root) if v.severity == "error"]


def test_default_tree_names_no_machine_path_and_validates(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root, coords=True)
    assert str(tmp_path) not in _all_text(root)          # no absolute path anywhere
    assert _errors(root) == []


def test_portable_tree_validates_after_a_move_with_no_step(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root, coords=True)
    moved = tmp_path / "elsewhere" / "deep" / "tree"
    shutil.copytree(root, moved)
    shutil.rmtree(root)                                  # the original place is gone
    assert _errors(moved) == []


def test_manifest_stores_skill_src_relative_and_load_resolves_it(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root)
    raw = json.loads((root / "skilltree.json").read_text())
    leaf = raw["skilltree"]["children"][1]
    assert not Path(leaf["skill_src"]).is_absolute()
    loaded = SkillTree.load(root / "skilltree.json")
    assert Path(loaded.root.children[1].skill_src).resolve() == (tmp_path / "src" / "b").resolve()


def test_localize_writes_absolute_and_still_validates(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root, localize=True)
    body = node_skill_md(root, "root").read_text()
    assert str(node_skill_md(root / "a", "a").resolve()) in body
    assert _errors(root) == []


def test_emit_switches_between_forms(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root, coords=True)
    assert emit(root, localize=True)["ok"]
    assert str(root.resolve()) in node_skill_md(root, "0-root").read_text()
    assert _errors(root) == []
    assert emit(root)["ok"]                              # default: portable again
    assert str(tmp_path) not in _all_text(root)
    assert _errors(root) == []


def test_project_localizes_the_projected_tree(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root, coords=True)
    skills = tmp_path / "user" / "skills"
    links = project(root, skills, policy="progressive")
    assert links and all(p.exists() for p in links)
    seen = (skills / "0-root" / "SKILL.md").read_text()   # read THROUGH the symlink
    crumb = str(node_skill_md(root / "a", "0.1-a").resolve())
    assert crumb in seen and Path(crumb).is_file()


def test_relink_switches_paths_and_touches_nothing_else(tmp_path: Path):
    root = tmp_path / "tree"
    materialize(_tree(tmp_path), root)                   # no coords: names must stay plain
    before = sorted(str(p.relative_to(root)) for p in root.rglob("SKILL.md"))
    assert relink(root, localize=True)["ok"]
    assert str(root.resolve()) in node_skill_md(root, "root").read_text()
    assert _errors(root) == []
    assert relink(root)["ok"]
    assert str(tmp_path) not in _all_text(root)
    assert sorted(str(p.relative_to(root)) for p in root.rglob("SKILL.md")) == before
    assert _errors(root) == []
