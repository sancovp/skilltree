"""Metaformal self-tests for the discover → cohere → emit front half.

These don't assert against a hand-built fixture's expected string — they TRIGGER
the real operations on a real temp filesystem and OBSERVE the state-change (the
tree that appears, the findings the gate emits, the flat dirs that vanish). The
filesystem is the oracle. (Frozen 2026-06-18 after the live run that built them.)
"""
from __future__ import annotations

import os
from pathlib import Path

from skilltree import materialize, SkillTree, TreeNode
from skilltree.cohere import cohere, discover, emit, unemit


def _flat_forest(d: Path, names) -> Path:
    cs = d / ".claude" / "skills"
    for n in names:
        (cs / n).mkdir(parents=True)
        (cs / n / "SKILL.md").write_text(f"---\nname: {n}\ndescription: the {n} skill\n---\n\nbody of {n}\n")
    return d


def test_bare_forest_is_flagged_then_rooted(tmp_path):
    """A flat .claude/skills (no root, no coords) is the rule-01 violation; emit
    --root-forest relocates the leaves into a nested tree and it goes coherent."""
    d = _flat_forest(tmp_path, ["alpha", "beta", "gamma"])

    before = cohere(d)
    assert any(f.kind == "bare_forest" for f in before)
    assert any(f.kind == "uncoordinated" for f in before)

    rep = emit(d, root_forest=True, forest_name="myforest")
    assert rep["ok"] and rep["synthesized_root"] and rep["nodes"] == 4

    # the leaves were RELOCATED into nested node-dirs (so they stop auto-loading)
    assert not (d / ".claude" / "skills" / "alpha").exists()       # old flat copy gone
    moved = d / "alpha" / ".claude" / "skills" / "0.1-alpha" / "SKILL.md"
    assert moved.exists() and "body of alpha" in moved.read_text()  # content preserved

    # and the whole thing is now coherent
    assert cohere(d) == []


def test_discover_reconstructs_a_nested_tree(tmp_path):
    """A materialized tree, read back from disk, reproduces its shape + coords."""
    tree = SkillTree(TreeNode("root", "sc", description="r", children=[
        TreeNode("a", "cor", description="a", children=[TreeNode("a1", "ac", description="a1")]),
        TreeNode("b", "ac", description="b"),
    ]))
    materialize(tree, tmp_path / "t", coords=True)

    live = discover(tmp_path / "t")
    names = {n.name for n in live.nodes()}
    assert {"root", "a", "a1", "b"} <= names
    # discover read the coords off the disk identities
    assert live.root.coord == "0"
    assert cohere(tmp_path / "t") == []     # freshly materialized = coherent


def test_cohere_catches_drift(tmp_path):
    """Decoherence: a skill dropped flatly into a coherent tree is caught as a stray
    (the thing the cron notifies on)."""
    d = _flat_forest(tmp_path, ["x", "y"])
    emit(d, root_forest=True, forest_name="t")
    assert cohere(d) == []

    # someone drops a skill into the root's .claude/skills out of band
    sneaky = d / ".claude" / "skills" / "sneaky"
    sneaky.mkdir()
    (sneaky / "SKILL.md").write_text("---\nname: sneaky\ndescription: snuck in\n---\nx\n")

    findings = cohere(d)
    assert any(f.kind == "stray_skill" and "sneaky" in f.detail for f in findings)


def test_emit_in_place_refreshes_breadcrumbs(tmp_path):
    """emit on an existing tree rewrites breadcrumbs/coords in place (no rmtree):
    after corrupting a branch's breadcrumbs, emit restores coherence."""
    d = _flat_forest(tmp_path, ["m", "n"])
    emit(d, root_forest=True, forest_name="t")

    # corrupt the root's SKILL.md (wipe its Descend block)
    root_md = d / ".claude" / "skills" / "0-t" / "SKILL.md"
    root_md.write_text("---\nname: 0-t\ndescription: [0] t\n---\n\njust a body, no breadcrumbs\n")
    assert any(f.kind == "stale_breadcrumb" for f in cohere(d))

    emit(d)                                  # in-place re-cohere (manifest present)
    assert cohere(d) == []


def test_mixed_coord_flat_forest_is_still_a_bare_forest(tmp_path):
    """REGRESSION (found on the real ~/.claude, 2026-06-18): a flat forest where a
    FEW leaves carry leftover coord prefixes must still report `bare_forest` — a
    coord-named leaf in a flat pile is NOT a root. (The sandboxes were cleanly flat
    or cleanly coordinated; the real dir was mixed, and the mix returned a false
    'nominal' until discover stopped inferring an owner from a pile.)"""
    cs = tmp_path / ".claude" / "skills"
    for n in ("0-leftover", "0.1-also-leftover", "plain-a", "plain-b", "plain-c"):
        (cs / n).mkdir(parents=True)
        (cs / n / "SKILL.md").write_text(f"---\nname: {n}\ndescription: {n}\n---\nbody\n")
    findings = cohere(tmp_path / ".claude")
    assert any(f.kind == "bare_forest" for f in findings), [str(f) for f in findings]


def test_emit_is_lossless_and_reversible(tmp_path):
    """emit moves the WHOLE skill dir (baggage preserved, unlike the old body-only
    re-render) and journals it; unemit replays the journal backwards for an exact
    round-trip. (Isaac's 'if we move it we have to cache what happened' requirement.)"""
    d = tmp_path / "proj"
    cs = d / ".claude" / "skills"
    (cs / "alpha").mkdir(parents=True)
    orig_md = "---\nname: alpha\ndescription: a\n---\n\nbody alpha\n"
    (cs / "alpha" / "SKILL.md").write_text(orig_md)
    (cs / "alpha" / "reference.md").write_text("BAGGAGE")     # the file the old emit dropped
    (cs / "beta").mkdir(parents=True)
    (cs / "beta" / "SKILL.md").write_text("---\nname: beta\ndescription: b\n---\n\nbody beta\n")

    rep = emit(d, root_forest=True, forest_name="proj")
    assert rep["moves"] == 2 and (d / ".emit-journal.json").exists()
    # baggage survived the move into the nested node-dir
    moved_ref = d / "alpha" / ".claude" / "skills" / "0.1-alpha" / "reference.md"
    assert moved_ref.exists() and moved_ref.read_text() == "BAGGAGE"

    # reverse it → exact round-trip
    rep2 = unemit(d)
    assert rep2["ok"] and rep2["moved_back"] == 2
    assert (cs / "alpha" / "SKILL.md").read_text() == orig_md          # SKILL.md restored verbatim
    assert (cs / "alpha" / "reference.md").read_text() == "BAGGAGE"    # baggage restored
    assert (cs / "beta" / "SKILL.md").exists()
    assert not (d / "alpha").exists()              # nested scaffold pruned
    assert not (d / "skilltree.json").exists()     # synthesized manifest removed
    assert not (d / ".emit-journal.json").exists() # journal consumed


def test_emit_handles_symlinked_skills(tmp_path):
    """REGRESSION (found dogfooding the real dev forest, 2026-06-18): 4 of 8 dev
    skills are SYMLINKS (installed skills point at package sources). The naive move
    broke (relocate the link → relative target breaks → mkdir over a dead link).
    Fix: de-symlink — copy the resolved content into the node-dir, journal the link,
    restore it exactly on unemit."""
    # a real skill the symlink will point at, OUTSIDE the forest
    target = tmp_path / "lib" / "linked-skill"
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text("---\nname: linked-skill\ndescription: via symlink\n---\nbody\n")
    (target / "reference.md").write_text("LINKED-BAGGAGE")

    d = tmp_path / "proj"
    cs = d / ".claude" / "skills"
    (cs / "real").mkdir(parents=True)
    (cs / "real" / "SKILL.md").write_text("---\nname: real\ndescription: r\n---\nbody\n")
    os.symlink(target, cs / "linked-skill")              # the symlink'd skill

    rep = emit(d, root_forest=True, forest_name="proj")
    assert rep["ok"] and rep["moves"] == 2               # both the real dir and the link relocated

    # the symlink was DE-symlinked: content (incl. baggage) copied into the node-dir
    moved = d / "linked-skill" / ".claude" / "skills" / "0.1-linked-skill"
    assert (moved / "reference.md").read_text() == "LINKED-BAGGAGE"
    assert not (cs / "linked-skill").exists()            # original link gone
    assert cohere(d) == []                               # coherent

    # unemit restores the EXACT symlink + removes the copy; the link target is untouched
    rep2 = unemit(d)
    assert rep2["ok"]
    restored = cs / "linked-skill"
    assert restored.is_symlink() and Path(os.readlink(restored)) == target
    assert (target / "reference.md").read_text() == "LINKED-BAGGAGE"   # source never touched
    assert not (d / "linked-skill").exists()             # copy pruned


def test_breadcrumbs_instruct_the_read_tool_not_cat(tmp_path):
    """REGRESSION (verified 2026-06-18): only the Read TOOL injects a dir's layer; a
    Bash `cat` loads nothing. So the generated descend breadcrumbs must say Read,
    never `cat <path>` — else descent silently fails."""
    cs = tmp_path / "proj" / ".claude" / "skills"
    for n in ("a", "b"):
        (cs / n).mkdir(parents=True)
        (cs / n / "SKILL.md").write_text(f"---\nname: {n}\ndescription: {n}\n---\nbody\n")
    emit(tmp_path / "proj", root_forest=True, forest_name="proj")

    root_md = (tmp_path / "proj" / ".claude" / "skills" / "0-proj" / "SKILL.md").read_text()
    assert "## Descend" in root_md
    assert "Read `" in root_md                    # the breadcrumb verb is Read…
    assert "`cat " not in root_md                 # …never a literal `cat <path>`
    assert "Read tool" in root_md                 # and it says so explicitly
