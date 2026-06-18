"""Tests: coordinate addressing — every node gets a coord, skill names carry it."""
from __future__ import annotations

from pathlib import Path

from skilltree import (
    SkillTree,
    TreeNode,
    assign_coords,
    is_valid,
    link_tree,
    materialize,
    skill_name,
)


def _tree():
    return SkillTree(TreeNode("root", "sc", children=[
        TreeNode("a", "cor", children=[TreeNode("a1", "ac"), TreeNode("a2", "ac")]),
        TreeNode("b", "cor"),
    ]))


def test_assign_coords_addresses_every_node():
    tree = _tree()
    assign_coords(tree.root)
    coords = {n.name: n.coord for n in tree.nodes()}
    assert coords == {"root": "0", "a": "0.1", "a1": "0.1.1", "a2": "0.1.2", "b": "0.2"}
    assert skill_name(tree.root) == "0-root"


def test_materialize_with_coords_prefixes_skill_names(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root, coords=True)
    assert is_valid(root)                                   # validator coord-aware
    # the skill dirs + frontmatter carry the coordinate
    assert (root / ".claude" / "skills" / "0-root" / "SKILL.md").is_file()
    assert (root / "a" / ".claude" / "skills" / "0.1-a" / "SKILL.md").is_file()
    assert (root / "a" / "a1" / ".claude" / "skills" / "0.1.1-a1" / "SKILL.md").is_file()
    assert "name: 0.1-a" in (root / "a" / ".claude" / "skills" / "0.1-a" / "SKILL.md").read_text()


def test_link_tree_surfaces_coord_named_symlinks(tmp_path: Path):
    repo = tmp_path / "t"
    materialize(_tree(), repo, coords=True)
    user = tmp_path / "user_skills"
    links = link_tree(repo, user_skills_dir=user)
    assert {p.name for p in links} == {"0-root", "0.1-a", "0.2-b"}     # coord-prefixed at the top
    for p in links:
        assert (p / "SKILL.md").is_file()


def test_coords_off_is_unchanged(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root)                              # default: no coords
    assert is_valid(root)
    assert (root / ".claude" / "skills" / "root" / "SKILL.md").is_file()
    assert not (root / ".claude" / "skills" / "0-root").exists()
