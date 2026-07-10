"""Tome bind-op tests (Move 1): fold, the generated ## Frameworks table, the
validate round-trip, and project(policy="flat"/"progressive")."""
from __future__ import annotations

import re
from pathlib import Path

from skilltree import (
    SkillTree,
    TreeNode,
    fold,
    is_valid,
    link_tree,
    materialize,
    project,
    validate,
)
from skilltree.cohere import emit
from skilltree.materialize import node_skill_md


def _framework(tmp_path: Path, name: str, desc: str = "does the thing") -> Path:
    d = tmp_path / f"fw-{name}"
    d.mkdir()
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\n---\n\nThe {name} framework.\n")
    return d


def _volume_tree(tmp_path: Path) -> Path:
    tree = SkillTree(TreeNode("my-tome", "sc", description="the tome root", children=[
        TreeNode("patterns", "sc", description="the pattern volume"),
    ]))
    root = tmp_path / "tome_tree"
    materialize(tree, root)
    return root


def test_fold_adds_row_and_emits_table(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fw = _framework(tmp_path, "alpha", "greek things")
    rep = fold(fw, into="patterns", tree_root=root)
    assert rep["ok"] and not rep["updated"] and rep["rows"] == 1
    # manifest carries the row
    tree = SkillTree.load(root / "skilltree.json")
    node = next(n for n in tree.nodes() if n.name == "patterns")
    assert node.frameworks[0]["name"] == "alpha"
    assert node.frameworks[0]["skill_path"].endswith("SKILL.md")
    # SKILL.md carries the generated table with the nomicon-atomize-parseable cell
    body = node_skill_md(root / "patterns", "patterns").read_text()
    assert "## Frameworks" in body
    assert "| Framework | What it's for | Framework skill |" in body
    assert re.search(r"\| alpha \| greek things \| alpha \(/.*?/SKILL\.md\) \|", body)
    assert is_valid(root)


def test_fold_is_idempotent_one_row_per_framework(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fw = _framework(tmp_path, "alpha")
    assert fold(fw, into="patterns", tree_root=root)["rows"] == 1
    rep = fold(fw, into="patterns", tree_root=root, what_for="updated purpose")
    assert rep["updated"] and rep["rows"] == 1          # updated in place, not duplicated
    body = node_skill_md(root / "patterns", "patterns").read_text()
    assert body.count("| alpha |") == 1
    assert "updated purpose" in body


def test_fold_bad_targets_are_reported(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fw = _framework(tmp_path, "alpha")
    assert not fold(fw, into="nope", tree_root=root)["ok"]
    empty = tmp_path / "not-a-framework"
    empty.mkdir()
    assert not fold(empty, into="patterns", tree_root=root)["ok"]


def test_emit_regenerates_table_from_model(tmp_path: Path):
    # a re-cohere (emit) must RE-EMIT the folded table, never wipe it
    root = _volume_tree(tmp_path)
    fold(_framework(tmp_path, "alpha"), into="patterns", tree_root=root)
    rep = emit(root)
    assert rep["ok"]
    tree = SkillTree.load(root / "skilltree.json")
    node = next(n for n in tree.nodes() if n.name == "patterns")
    smd = root / "patterns" / ".claude" / "skills" / f"{node.coord}-patterns" / "SKILL.md"
    body = smd.read_text()
    assert body.count("## Frameworks") == 1             # regenerated once, not doubled
    assert "| alpha |" in body


def test_validate_round_trip_catches_drift(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fw = _framework(tmp_path, "alpha")
    fold(fw, into="patterns", tree_root=root)
    assert is_valid(root)
    # dead target: the framework dir vanishes → error
    (fw / "SKILL.md").rename(fw / "GONE.md")
    errs = [v for v in validate(root) if v.severity == "error"]
    assert any("does not resolve" in v.message for v in errs)
    (fw / "GONE.md").rename(fw / "SKILL.md")
    # missing table: SKILL.md hand-stripped of the section → error
    smd = node_skill_md(root / "patterns", "patterns")
    smd.write_text(re.sub(r"\n+## Frameworks\b.*\Z", "\n", smd.read_text(), flags=re.S))
    errs = [v for v in validate(root) if v.severity == "error"]
    assert any("no ## Frameworks table" in v.message for v in errs)


def test_validate_warns_on_undeclared_table_row(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fold(_framework(tmp_path, "alpha"), into="patterns", tree_root=root)
    smd = node_skill_md(root / "patterns", "patterns")
    smd.write_text(smd.read_text() + "| ghost | not in manifest | ghost (/nowhere/SKILL.md) |\n")
    warns = [v for v in validate(root) if v.severity == "warning"]
    assert any("ghost" in v.message and "not declared" in v.message for v in warns)


def test_project_flat_symlinks_rows_and_holder(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fw_a = _framework(tmp_path, "alpha")
    fw_b = _framework(tmp_path, "beta")
    fold(fw_a, into="patterns", tree_root=root)
    fold(fw_b, into="patterns", tree_root=root)
    target = tmp_path / "flat_skills"
    links = project(root, target, policy="flat", node="patterns")
    names = {p.name for p in links}
    assert names == {"alpha", "beta", "patterns"}       # every row + the holder
    for p in links:
        assert p.is_symlink() and (p / "SKILL.md").is_file()
    # the originals stay the source of truth (symlinks, not copies)
    assert (target / "alpha").resolve() == fw_a.resolve()


def test_project_flat_relative_links_and_reruns_cleanly(tmp_path: Path):
    root = _volume_tree(tmp_path)
    fold(_framework(tmp_path, "alpha"), into="patterns", tree_root=root)
    target = tmp_path / "flat_skills"
    project(root, target, policy="flat", node="patterns", link="relative")
    raw = (target / "alpha").readlink()
    assert not raw.is_absolute()                        # relative = portable together
    # idempotent re-run
    links = project(root, target, policy="flat", node="patterns", link="relative")
    assert {p.name for p in links} == {"alpha", "patterns"}


def test_project_flat_self_clobber_guard(tmp_path: Path):
    # projecting INTO the holder's own dir must never destroy the source
    root = _volume_tree(tmp_path)
    fold(_framework(tmp_path, "alpha"), into="patterns", tree_root=root)
    inside = root / "patterns" / ".claude" / "skills"
    links = project(root, inside, policy="flat", node="patterns")
    assert "patterns" not in {p.name for p in links}    # holder self-link skipped
    assert node_skill_md(root / "patterns", "patterns").is_file()   # source intact


def test_relative_fold_survives_relocation(tmp_path: Path):
    # a repo-committed tome: relative rows must validate + project from ANY checkout path
    site_a = tmp_path / "checkout_a"
    site_a.mkdir()
    root = _volume_tree(site_a)
    fw = _framework(site_a, "alpha")
    rep = fold(fw, into="patterns", tree_root=root, relative=True)
    assert rep["ok"] and not Path(rep["row"]["skill_path"]).is_absolute()
    assert is_valid(root)
    # relocate the WHOLE checkout (tree + framework move together, like a fresh CI clone)
    site_b = tmp_path / "checkout_b"
    site_a.rename(site_b)
    root_b = site_b / "tome_tree"
    # breadcrumbs are absolute by design → a moved tree needs the localize step first:
    # emit re-coheres at the NEW location from the manifest (the portable canon). The
    # relative tome rows need no rewrite — that is the point of --relative.
    assert emit(root_b)["ok"]
    assert is_valid(root_b)                             # emit + validate = the CI gate flow
    links = project(root_b, tmp_path / "flat_b", policy="flat", node="patterns")
    assert (tmp_path / "flat_b" / "alpha").resolve() == (site_b / "fw-alpha").resolve()
    # emit coordinatized the tree, so the holder projects under its coord identity
    assert {p.name for p in links} == {"alpha", "0.1-patterns"}


def test_project_progressive_matches_link_tree(tmp_path: Path):
    root = _volume_tree(tmp_path)
    a = tmp_path / "user_a"
    b = tmp_path / "user_b"
    via_project = {p.name for p in project(root, a, policy="progressive")}
    via_link_tree = {p.name for p in link_tree(root, user_skills_dir=b)}
    assert via_project == via_link_tree == {"my-tome", "patterns"}
