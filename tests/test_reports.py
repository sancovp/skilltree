"""Tests: the skill-reports store (the observe→improve queue)."""
from __future__ import annotations

from pathlib import Path

from skilltree import list_reports, mark_problem, report_missed, reports_summary, resolve


def test_report_missed_and_list(tmp_path: Path):
    rp = tmp_path / "reports.json"
    e = report_missed(rp, needed="a CSV linter", happened="hand-rolled it", suggests="csv-lint: validate CSVs", by="agent")
    assert e["id"] == "r1" and e["kind"] == "missed_skill" and e["status"] == "open"
    rows = list_reports(rp)
    assert len(rows) == 1 and rows[0]["needed"] == "a CSV linter"


def test_mark_problem(tmp_path: Path):
    rp = tmp_path / "reports.json"
    mark_problem(rp, skill="deep-research", expected="should have triggered", happened="answered from memory")
    assert list_reports(rp, kind="expected_not_used")[0]["skill"] == "deep-research"


def test_summary_and_resolve(tmp_path: Path):
    rp = tmp_path / "reports.json"
    report_missed(rp, needed="x", happened="y")
    mark_problem(rp, skill="s", expected="e", happened="h")
    s = reports_summary(rp)
    assert s == {"total": 2, "open": 2, "open_by_kind": {"missed_skill": 1, "expected_not_used": 1}}
    resolve(rp, "r1", resolution="created csv-lint skill")
    assert reports_summary(rp)["open"] == 1                 # r1 closed
    assert list_reports(rp) == [r for r in list_reports(rp) if r["status"] == "open"]
    assert "r1" not in {r["id"] for r in list_reports(rp)}   # open list excludes resolved
