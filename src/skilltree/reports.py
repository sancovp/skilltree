"""The feedback store — the observe→improve half of the Skill OS.

Reports accumulate the gaps and problems found *in use*, so an improver can act
on them later. Two report kinds to start:

  - `missed_skill`      — a needed skill didn't exist (filed by the agent, or by
                          the user telling the agent "you missed X").
  - `expected_not_used` — a skill SHOULD have fired for a task but didn't
                          ("expected xyz but the skill wasn't used").

`report-missed-skill` (the shipped skill) calls `report_missed` via the CLI. An
improver agent reads the open reports, then creates/improves skills and calls
`resolve` to close them.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

DEFAULT_REPORTS = Path.home() / ".claude" / "skill-reports.json"


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def _save(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def file_report(reports_path: str | Path, *, kind: str, by: str, now: str | None = None,
                **fields: Any) -> dict:
    path = Path(reports_path)
    rows = _load(path)
    entry = {"id": f"r{len(rows) + 1}", "kind": kind, "by": by, "at": now or _now(),
             "status": "open", **fields}
    rows.append(entry)
    _save(path, rows)
    return entry


def report_missed(reports_path: str | Path = DEFAULT_REPORTS, *, needed: str, happened: str,
                  suggests: str | None = None, by: str = "agent", now: str | None = None) -> dict:
    """File a missed-skill report: a capability was needed but no skill existed."""
    return file_report(reports_path, kind="missed_skill", by=by, now=now,
                       needed=needed, happened=happened, suggests=suggests)


def mark_problem(reports_path: str | Path = DEFAULT_REPORTS, *, skill: str, expected: str,
                 happened: str, by: str = "user", now: str | None = None) -> dict:
    """Mark 'expected this skill to be used, but it wasn't' — feeds the improver."""
    return file_report(reports_path, kind="expected_not_used", by=by, now=now,
                       skill=skill, expected=expected, happened=happened)


def list_reports(reports_path: str | Path = DEFAULT_REPORTS, *, kind: str | None = None,
                 status: str | None = "open") -> list[dict]:
    rows = _load(Path(reports_path))
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    if status:
        rows = [r for r in rows if r.get("status") == status]
    return rows


def summary(reports_path: str | Path = DEFAULT_REPORTS) -> dict:
    rows = _load(Path(reports_path))
    open_rows = [r for r in rows if r.get("status") == "open"]
    by_kind: dict[str, int] = {}
    for r in open_rows:
        by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
    return {"total": len(rows), "open": len(open_rows), "open_by_kind": by_kind}


def resolve(reports_path: str | Path, report_id: str, *, resolution: str,
            by: str = "improver", now: str | None = None) -> dict:
    """Close a report (after creating/improving the skill it asked for)."""
    path = Path(reports_path)
    rows = _load(path)
    for r in rows:
        if r["id"] == report_id:
            r["status"] = "resolved"
            r["resolution"] = resolution
            r["resolved_by"] = by
            r["resolved_at"] = now or _now()
            _save(path, rows)
            return r
    raise KeyError(f"no report {report_id!r}")
