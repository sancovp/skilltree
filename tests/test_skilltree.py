"""SkillTree tests: the `cat`-breadcrumb nested tree, and its failure modes."""
from __future__ import annotations

from pathlib import Path

from skilltree import SkillTree, TreeNode, is_valid, materialize, validate
from skilltree.materialize import node_skill_md


def _tree() -> SkillTree:
    return SkillTree(TreeNode("cc-skill-tree", "sc", children=[
        TreeNode("a", "cor", children=[TreeNode("a1", "ac"), TreeNode("a2", "ac")]),
        TreeNode("b", "cor"),
    ]))


def test_materialize_nested_dirs_and_valid(tmp_path: Path):
    root = tmp_path / "cc_tree_test"
    materialize(_tree(), root)
    assert is_valid(root)
    # root skill is the only thing in the root .claude
    assert node_skill_md(root, "cc-skill-tree").is_file()
    # children are NESTED dirs (siblings of the parent .claude)
    assert node_skill_md(root / "a", "a").is_file()
    assert node_skill_md(root / "a" / "a1", "a1").is_file()


def test_root_body_has_cat_breadcrumbs_for_each_child(tmp_path: Path):
    root = tmp_path / "cc_tree_test"
    materialize(_tree(), root)
    body = node_skill_md(root, "cc-skill-tree").read_text()
    assert "cat" in body
    assert str(node_skill_md(root / "a", "a").resolve()) in body
    assert str(node_skill_md(root / "b", "b").resolve()) in body


def test_dead_breadcrumb_is_caught(tmp_path: Path):
    root = tmp_path / "cc_tree_test"
    materialize(_tree(), root)
    # move a child dir away → the parent's breadcrumb now points nowhere
    (root / "a" / "a1").rename(root / "a" / "moved")
    issues = [v for v in validate(root) if v.severity == "error"]
    assert any("breadcrumb" in v.message for v in issues)
    assert not is_valid(root)


def test_missing_skill_md_is_caught(tmp_path: Path):
    root = tmp_path / "cc_tree_test"
    materialize(_tree(), root)
    node_skill_md(root / "b", "b").unlink()
    assert not is_valid(root)


def test_leaf_carries_actual_skill_content(tmp_path: Path):
    # a leaf can carry a real skill's body from skill_src
    src = tmp_path / "real-skill"
    src.mkdir()
    (src / "SKILL.md").write_text("---\nname: real-skill\ndescription: a real one\n---\n\nDO THE REAL THING.\n")
    tree = SkillTree(TreeNode("cc-skill-tree", "sc", children=[
        TreeNode("leaf", "skill", skill_src=str(src)),
    ]))
    root = tmp_path / "cc_tree_test"
    materialize(tree, root)
    assert is_valid(root)
    assert "DO THE REAL THING." in node_skill_md(root / "leaf", "leaf").read_text()


def test_json_round_trip_reorganizes_tree(tmp_path: Path):
    # the JSON drives organization; reload + rematerialize reflects edits
    root = tmp_path / "cc_tree_test"
    materialize(_tree(), root)
    manifest = SkillTree.load(root / "skilltree.json")
    assert [c.name for c in manifest.root.children] == ["a", "b"]
