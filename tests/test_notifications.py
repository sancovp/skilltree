"""Metaformal self-tests for the decoherence-cron's output: the self-managed
top-level `system_notifications` rule.

Trigger the real cohere→render→write on a sandbox and OBSERVE the rule file's
content flip between 'nominal' and ERROR. The file is the oracle. tmp_path only —
never ~/.claude/rules.
"""
from __future__ import annotations

from pathlib import Path

from skilltree.cohere import emit, write_notifications, watch, NOTIFY_RULE


def _flat(d: Path, names) -> Path:
    cs = d / ".claude" / "skills"
    for n in names:
        (cs / n).mkdir(parents=True)
        (cs / n / "SKILL.md").write_text(f"---\nname: {n}\ndescription: the {n} skill\n---\n\nbody {n}\n")
    return d


def test_nominal_tree_writes_systems_nominal(tmp_path):
    d = _flat(tmp_path / "proj", ["a", "b"])
    emit(d, root_forest=True, forest_name="proj")          # → coherent
    rules = tmp_path / "rules"
    rep = write_notifications(d, rules_dir=rules)
    assert rep["nominal"] is True and rep["errors"] == 0
    body = (rules / NOTIFY_RULE).read_text()
    assert "Systems nominal" in body
    assert "automatically managed by SkillTree" in body


def test_decohered_tree_writes_error_and_fix_instruction(tmp_path):
    d = _flat(tmp_path / "proj", ["a", "b", "c"])          # bare forest, never rooted
    rules = tmp_path / "rules"
    rep = write_notifications(d, rules_dir=rules)
    assert rep["nominal"] is False and rep["errors"] >= 1
    body = (rules / NOTIFY_RULE).read_text()
    assert "ERROR" in body and "bare_forest" in body
    assert "To fix" in body and "skilltree" in body
    assert "Systems nominal" not in body


def test_write_is_idempotent_when_unchanged(tmp_path):
    d = _flat(tmp_path / "proj", ["a"])
    emit(d, root_forest=True, forest_name="proj")
    rules = tmp_path / "rules"
    assert write_notifications(d, rules_dir=rules)["changed"] is True   # first write
    assert write_notifications(d, rules_dir=rules)["changed"] is False  # no churn


def test_watch_one_iteration_writes_the_rule(tmp_path):
    """watch(iterations=1) = a single cron tick; observe it produced the rule file
    without sleeping (a no-op sleep is injected)."""
    d = _flat(tmp_path / "proj", ["a", "b"])
    rules = tmp_path / "rules"
    rep = watch(d, rules_dir=rules, iterations=1, sleep=lambda *_: None)
    assert rep["checks"] == 1
    assert (rules / NOTIFY_RULE).exists()
