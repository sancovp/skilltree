"""Tests: surfacing a tree/forest at the top-level user .claude/skills via symlinks."""
from __future__ import annotations

from pathlib import Path

from skilltree import (
    SkillTree,
    TreeNode,
    build_forest,
    link_tree,
    list_links,
    materialize,
    unlink,
)


def _tree(root="cc-skill-tree"):
    return SkillTree(TreeNode(root, "sc", children=[
        TreeNode("reason", "cor", children=[TreeNode("simplify", "ac")]),
        TreeNode("debug", "cor"),
    ]))


def test_link_tree_surfaces_root_and_branches(tmp_path: Path):
    repo = tmp_path / "tree"
    materialize(_tree(), repo)
    user = tmp_path / "user_skills"
    links = link_tree(repo, user_skills_dir=user)
    names = {p.name for p in links}
    assert names == {"cc-skill-tree", "reason", "debug"}     # root + first-layer branches
    # each symlink resolves to a real SKILL.md at the top level
    for p in links:
        assert p.is_symlink()
        assert (p / "SKILL.md").is_file()
    # the deep leaf is NOT surfaced at the top (progressive disclosure)
    assert not (user / "simplify").exists()


def test_build_forest_makes_one_top_entry_over_many_trees(tmp_path: Path):
    a = tmp_path / "a"; materialize(_tree("alpha"), a)
    b = tmp_path / "b"; materialize(_tree("beta"), b)
    user = tmp_path / "user_skills"
    forest = tmp_path / "forest"
    link = build_forest("my-forest", [a, b], user_skills_dir=user, forest_dir=forest)
    assert link.is_symlink() and (link / "SKILL.md").is_file()
    body = (link / "SKILL.md").read_text()
    # the forest root breadcrumbs into each tree's root
    assert "alpha" in body and "beta" in body and "cat" in body


def test_list_and_unlink(tmp_path: Path):
    repo = tmp_path / "tree"; materialize(_tree(), repo)
    user = tmp_path / "user_skills"
    link_tree(repo, user_skills_dir=user)
    listed = {x["name"]: x["resolves"] for x in list_links(user)}
    assert listed.get("cc-skill-tree") is True
    removed = unlink(user, "cc-skill-tree", "reason", "debug")
    assert set(removed) == {"cc-skill-tree", "reason", "debug"}
    assert list_links(user) == []
