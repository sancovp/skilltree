"""GlyphSteer integration: facet the skill search by an LLM-authored glyph + legend."""
from pathlib import Path

import pytest

from skilltree.search import build_index, search

glyphsteer = pytest.importorskip("glyphsteer")


def _skill(root: Path, name: str, body: str, glyphs: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: about {name}\nglyphs: {glyphs}\n---\n{body}\n",
        encoding="utf-8")


def _corpus(tmp_path: Path):
    # an LLM authors a quality vocabulary and grades three skills
    V = glyphsteer.author([
        {"name": "trusted", "glyph": "🏆", "description": "verified, production-grade"},
        {"name": "draft", "glyph": "✏️", "description": "unverified draft"},
    ])
    root = tmp_path / "skills"
    _skill(root, "deploy", "how to deploy the service safely", "🏆")
    _skill(root, "scratch", "rough notes on how to deploy", "✏️")
    _skill(root, "rollback", "how to roll back a deploy", "🏆")
    return root, V


def test_facet_by_glyph_filters_skills(tmp_path: Path):
    root, V = _corpus(tmp_path)
    con = build_index(root, vocab=V)
    trusted = {h["name"] for h in search(con, "deploy", facet="🏆", vocab=V)}
    assert trusted == {"deploy", "rollback"}            # only the trusted ones
    draft = {h["name"] for h in search(con, "deploy", facet="✏️", vocab=V)}
    assert draft == {"scratch"}


def test_unfaceted_search_unaffected_and_returns_glyphs(tmp_path: Path):
    root, V = _corpus(tmp_path)
    con = build_index(root, vocab=V)
    hits = search(con, "deploy")
    assert {h["name"] for h in hits} == {"deploy", "scratch", "rollback"}
    assert any(h["glyphs"] == "🏆" for h in hits)        # glyph code surfaced for display


def test_works_without_vocab_backward_compatible(tmp_path: Path):
    root, _ = _corpus(tmp_path)
    con = build_index(root)                              # no vocab
    assert {h["name"] for h in search(con, "deploy")} == {"deploy", "scratch", "rollback"}
