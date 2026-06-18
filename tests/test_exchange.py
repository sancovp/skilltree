"""Exchange tests: many trees + a master, built and validated."""
from __future__ import annotations

import json
from pathlib import Path

from skilltree import SkillTree, TreeNode, build_exchange, exchange_is_valid, load_exchange
from skilltree.materialize import node_skill_md


def _two_tree_exchange(tmp_path: Path) -> Path:
    # two member tree manifests
    cog = SkillTree(TreeNode("cognition", "sc", children=[TreeNode("reason", "cor")]))
    wri = SkillTree(TreeNode("writing", "sc", children=[TreeNode("draft", "cor")]))
    cog.save(tmp_path / "cognition.skilltree.json")
    wri.save(tmp_path / "writing.skilltree.json")
    manifest = {
        "name": "my-exchange", "master": "cc-master",
        "trees": [
            {"name": "cognition", "manifest": "cognition.skilltree.json"},
            {"name": "writing", "manifest": "writing.skilltree.json"},
        ],
    }
    mpath = tmp_path / "exchange.json"
    mpath.write_text(json.dumps(manifest))
    return mpath


def test_build_exchange_master_and_members(tmp_path: Path):
    mpath = _two_tree_exchange(tmp_path)
    ex = load_exchange(mpath)
    repo = tmp_path / "repo"
    master = build_exchange(ex, repo)
    assert master.is_file()
    assert exchange_is_valid(repo, ex)
    # master breadcrumbs into each member tree's root
    body = master.read_text()
    assert str(node_skill_md(repo / "trees" / "cognition", "cognition").resolve()) in body
    assert str(node_skill_md(repo / "trees" / "writing", "writing").resolve()) in body
    # each member tree is materialized + valid on its own
    assert node_skill_md(repo / "trees" / "cognition" / "reason", "reason").is_file()


def test_dead_master_breadcrumb_caught(tmp_path: Path):
    from skilltree import validate_exchange
    mpath = _two_tree_exchange(tmp_path)
    ex = load_exchange(mpath)
    repo = tmp_path / "repo"
    build_exchange(ex, repo)
    # nuke a member tree → master breadcrumb to it now dies
    import shutil
    shutil.rmtree(repo / "trees" / "writing")
    issues = [v for v in validate_exchange(repo, ex) if v.severity == "error"]
    assert issues
