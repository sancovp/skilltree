"""Metaformal self-test: emit (tree-ify) → unemit is LOSSLESS and reversible.

Triggers the real moves on a real sandbox fs with the two things that broke the old
emit — baggage (non-SKILL.md files) and a symlink'd skill — and OBSERVES that the
forest re-coheres into a tree, then reverses byte-for-byte. The filesystem is the oracle.
"""
from __future__ import annotations

import os
from pathlib import Path

from skilltree.cohere import emit, unemit, cohere


def _skill(d: Path, name: str, body: str = "body") -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: the {name} skill\n---\n\n{body}\n")
    return d


def _snapshot(root: Path) -> dict:
    """Content snapshot: files → ('f', bytes), symlinks → ('l', target), dirs → ('d',)."""
    snap: dict[str, tuple] = {}
    for p in sorted(root.rglob("*")):
        rel = str(p.relative_to(root))
        if p.is_symlink():
            snap[rel] = ("l", os.readlink(p))
        elif p.is_dir():
            snap[rel] = ("d",)
        else:
            snap[rel] = ("f", p.read_bytes())
    return snap


def test_emit_then_unemit_is_byte_identical(tmp_path):
    proj = tmp_path / "proj"
    cs = proj / ".claude" / "skills"

    # (1) a real skill WITH BAGGAGE — the thing the old emit destroyed
    a = _skill(cs / "alpha", "alpha")
    (a / "reference.md").write_text("ALPHA REFERENCE — must survive\n")
    (a / "scripts").mkdir()
    (a / "scripts" / "run.sh").write_text("echo hello\n")
    # (2) a plain real skill
    _skill(cs / "beta", "beta")
    # (3) a SYMLINK'd skill pointing at an external served source
    served = _skill(tmp_path / "served" / "gamma", "gamma")
    os.symlink(served, cs / "gamma")

    before = _snapshot(cs)

    # tree-ify
    rep = emit(proj, root_forest=True, forest_name="proj")
    assert rep["ok"] and rep["synthesized_root"] and rep["moves"] == 3

    # baggage was carried WHOLE into the nested node-dir (not re-rendered away)
    ref = proj / "alpha" / ".claude" / "skills" / "0.1-alpha" / "reference.md"
    assert ref.exists() and "must survive" in ref.read_text()
    assert (proj / "alpha" / ".claude" / "skills" / "0.1-alpha" / "scripts" / "run.sh").exists()
    # the symlink was de-symlinked into a writable copy (so coords/breadcrumbs can be added)
    g = proj / "gamma" / ".claude" / "skills" / "0.3-gamma" / "SKILL.md"
    assert g.exists() and not g.is_symlink()
    # the original flat layer is gone; only the synthesized root remains there
    assert not (cs / "alpha").exists()
    assert (cs / "0-proj" / "SKILL.md").exists()
    # the root menu uses Read breadcrumbs (not cat) and the tree is coherent
    root_md = (cs / "0-proj" / "SKILL.md").read_text()
    assert "Read `" in root_md and "cat `" not in root_md
    assert cohere(proj) == []
    assert (proj / ".emit-journal.json").exists()

    # (4) reverse it — byte-for-byte
    urep = unemit(proj)
    assert urep["ok"]
    after = _snapshot(cs)
    assert after == before, "unemit did not restore the original tree exactly"
    # the receipts + synthesized structure are gone
    assert not (proj / ".emit-journal.json").exists()
    assert not (proj / "skilltree.json").exists()
    assert not (proj / "alpha").exists() and not (proj / "gamma").exists()
    # and the symlink is a symlink again, pointing where it did
    assert (cs / "gamma").is_symlink()
