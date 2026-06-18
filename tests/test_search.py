"""P6 search-arm tests: FTS5/BM25 + coordinate-scoped subtree search."""
from __future__ import annotations

from pathlib import Path

from skilltree import SkillTree, TreeNode, build_index, materialize, search, search_tree


def _tree() -> SkillTree:
    return SkillTree(TreeNode("cc-skill-tree", "sc", description="root of the cognition tree", children=[
        TreeNode("reason", "cor", description="how to reason carefully", children=[
            TreeNode("einstein", "cor", description="fix the invariant, run a thought experiment"),
        ]),
        TreeNode("debug", "cor", description="find the bug: symptom, repro, localize", children=[
            TreeNode("symptom-attn", "ac", description="attend to the symptom first"),
        ]),
    ]))


def test_search_finds_by_description(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root, coords=True)
    hits = search_tree(root, "thought experiment")
    assert any("einstein" in h["name"] for h in hits)


def test_search_ranks_relevant_first(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root, coords=True)
    hits = search_tree(root, "symptom repro localize")
    assert hits and "debug" in hits[0]["name"]


def test_coordinate_scope_restricts_to_subtree(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root, coords=True)
    con = build_index(root)
    # "attend" appears under the debug subtree (0.2). Scope to reason (0.1) → no hit.
    assert search(con, "attend symptom", scope_coord="0.2")          # found under debug
    assert search(con, "attend symptom", scope_coord="0.1") == []    # not under reason


def test_coords_are_carried_in_results(tmp_path: Path):
    root = tmp_path / "t"
    materialize(_tree(), root, coords=True)
    hits = search_tree(root, "reason")
    assert any(h["coord"] for h in hits)            # coordinate addresses come back with hits
