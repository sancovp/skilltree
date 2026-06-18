"""The folded `foldersearch` + `skillsearch` → `skilltree search`. ONE FTS5/BM25 engine; the
`--scope` coordinate filter is the only difference between coordinate-free and tree-aware search."""
from __future__ import annotations

from pathlib import Path

from skilltree.search import search_folder, build_index, search, DEFAULT_EXTS


def test_foldersearch_plain_folder_is_coordinate_free(tmp_path):
    """Any folder of text — no coordinates needed. (The former `foldersearch`.)"""
    (tmp_path / "a.md").write_text("# Kubernetes\ningress timeout tuning and retries\n")
    (tmp_path / "b.txt").write_text("refund policy: thirty days, no questions asked\n")
    hits = search_folder(tmp_path, "ingress timeout")
    assert hits and hits[0]["path"].endswith("a.md")
    assert hits[0]["coord"] == ""                       # coordinate-free


def test_skillsearch_scope_restricts_to_a_coordinate_subtree(tmp_path):
    """SKILL.md carrying <coord>-<name> frontmatter → --scope restricts to a subtree.
    (The former `skillsearch`, same engine.)"""
    def sk(coord: str, name: str) -> None:
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text(
            f"---\nname: {coord}-{name}\ndescription: d\n---\n\ndeploy rollback steps\n")
    sk("0.1", "alpha")
    sk("0.2", "beta")
    sk("0.2.1", "gamma")          # same terms, different branch / deeper

    allhits = search_folder(tmp_path, "deploy rollback")
    assert len(allhits) >= 3                              # unscoped finds all

    scoped = search_folder(tmp_path, "deploy rollback", scope_coord="0.2")
    assert {h["coord"] for h in scoped} == {"0.2", "0.2.1"}   # only 0.2 + its descendant


def test_one_engine_same_search_function(tmp_path):
    """foldersearch and skillsearch go through the SAME build_index + search; coord is just empty
    when the file has no <coord>-<name> name."""
    (tmp_path / "note.md").write_text("# Title\nsome uniquely searchable content here\n")
    con = build_index(tmp_path, exts=DEFAULT_EXTS)
    hits = search(con, "uniquely searchable")
    assert hits and hits[0]["coord"] == ""
