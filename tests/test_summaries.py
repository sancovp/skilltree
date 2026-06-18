"""Template node-summaries: branches become retrievable by descendant terms."""
from __future__ import annotations

from pathlib import Path

from skilltree import SkillTree, TreeNode, build_index, materialize, search
from skilltree.model import assign_coords, compose_summary


def _tree() -> SkillTree:
    return SkillTree(TreeNode("root", "sc", children=[
        TreeNode("debug", "cor", children=[TreeNode("symptom-localizer", "ac")]),
        TreeNode("reason", "cor", children=[TreeNode("invariant-finder", "ac")]),
    ]))


def test_compose_summary_packs_coord_and_reachable():
    root = _tree().root
    assign_coords(root)
    s = compose_summary(root.children[0], full=True)   # the "debug" branch
    assert "0.1" in s                                   # its coordinate
    assert "symptom-localizer" in s                     # a reachable descendant
    short = compose_summary(root.children[0])
    assert "symptom-localizer" in short and "Reachable" not in short  # short = immediate kids only


def test_branch_is_retrievable_by_a_descendant_term(tmp_path: Path):
    root_dir = tmp_path / "t"
    materialize(_tree(), root_dir, coords=True)
    con = build_index(root_dir)
    names = {h["name"] for h in search(con, "symptom-localizer")}
    assert any("symptom-localizer" in n for n in names)   # the leaf matches
    assert any("debug" in n for n in names)               # AND the branch (via its summary)
    # the sibling branch should NOT surface for an unrelated descendant term
    assert not any("reason" in n for n in names)


def test_internal_node_description_defaults_to_summary(tmp_path: Path):
    root_dir = tmp_path / "t"
    materialize(_tree(), root_dir, coords=True)
    # the root has no explicit description → it gets the composed "opens to ..." summary
    from skilltree.materialize import node_skill_md
    root_md = node_skill_md(root_dir, "0-root").read_text()
    assert "opens to 2 branch(es)" in root_md
    assert "Index summary" in root_md
