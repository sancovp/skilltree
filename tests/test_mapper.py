"""The folded `skillmap` → `skilltree map`. Verifies the single-CLAUDE.md rendering AND that it
uses skilltree's OWN coordinate code (assign_coords / skill_name) — no vendored copy."""
from __future__ import annotations

from pathlib import Path

from skilltree import assign_coords, skill_name
from skilltree.mapper import build_map, write_map, build_tree


def _skill(d: Path, name: str, desc: str) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\nbody of {name}\n")


def test_map_renders_the_three_sections_and_canonical_coords(tmp_path):
    root = tmp_path / "skills"
    _skill(root / "alpha", "alpha", "the alpha skill")
    _skill(root / "beta", "beta", "the beta skill")
    _skill(root / "beta" / "sub", "sub", "nested under beta")

    out = build_map(root)
    assert "## Folder Map" in out and "## Index (addressable)" in out and "## Branches" in out
    # coordinates from skilltree.assign_coords (root 0, children 0.1/0.2, nested 0.2.1)
    assert "0.1" in out and "0.2" in out and "0.2.1" in out
    # the addressable <coord>-<name> identity (skill_name) appears
    assert "0.1-alpha" in out
    # descriptions were read from frontmatter
    assert "the alpha skill" in out and "nested under beta" in out


def test_build_tree_uses_skilltree_coordinate_code(tmp_path):
    """The tree is skilltree TreeNodes; coords + identities come from model.py, not a copy."""
    root = tmp_path / "s"
    _skill(root / "a", "a", "x")
    _skill(root / "b", "b", "y")
    tree = assign_coords(build_tree(root))
    assert tree.coord == "0"
    assert tree.children[0].coord == "0.1" and tree.children[1].coord == "0.2"
    assert skill_name(tree.children[0]) == "0.1-a"      # the canonical <coord>-<name>
    # the dir path rides in skill_src (so the Index can show a relative path)
    assert Path(tree.children[0].skill_src).name == "a"


def test_write_map_creates_one_claude_md(tmp_path):
    root = tmp_path / "s"
    _skill(root / "a", "a", "x")
    dest = write_map(root)
    assert dest == root / "CLAUDE.md" and dest.exists()
    assert "skill map" in dest.read_text() and "0.1-a" in dest.read_text()
