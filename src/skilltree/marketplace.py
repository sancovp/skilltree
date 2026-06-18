"""Marketplace — a programmatic registry for skills, trees, and exchanges.

The real, local half of the roadmap's marketplace: you `publish()` an artifact to
a registry (a JSON file), mark it `public` if you want, and `search()` it. The
registry GROWS as artifacts are added. Whenever something is published public, a
`notify` hook fires — that hook is where a hosted service ("our system") plugs in.

Aspirational (needs a backend, not built here): the hosted marketplace endpoint
the notify hook would POST to, and cross-user discovery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import datetime as _dt
import json
from pathlib import Path
from typing import Callable

KINDS = ("skill", "tree", "exchange")


@dataclass
class Entry:
    name: str
    kind: str
    path: str
    version: str = "0.1.0"
    public: bool = False
    published_at: str = ""
    tags: list[str] = field(default_factory=list)


def _load(registry: Path) -> list[dict]:
    return json.loads(registry.read_text(encoding="utf-8")) if registry.is_file() else []


def _save(registry: Path, rows: list[dict]) -> None:
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def publish(
    registry: str | Path,
    name: str,
    path: str | Path,
    *,
    kind: str = "skill",
    public: bool = False,
    version: str = "0.1.0",
    tags: list[str] | None = None,
    notify: Callable[[Entry], None] | None = None,
    now: str | None = None,
) -> Entry:
    """Add (or update) an artifact in the registry. Fires `notify` if it's public."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    registry = Path(registry)
    entry = Entry(name=name, kind=kind, path=str(Path(path)), version=version, public=public,
                  published_at=now or _dt.datetime.now().isoformat(timespec="seconds"),
                  tags=tags or [])
    rows = [r for r in _load(registry) if r.get("name") != name]   # upsert by name
    rows.append(asdict(entry))
    _save(registry, rows)
    if public and notify is not None:
        notify(entry)          # ← where the hosted "notify our system" service plugs in
    return entry


def search(registry: str | Path, query: str | None = None, *, public_only: bool = False) -> list[dict]:
    rows = _load(Path(registry))
    if public_only:
        rows = [r for r in rows if r.get("public")]
    if query:
        q = query.lower()
        rows = [r for r in rows if q in r["name"].lower() or any(q in t.lower() for t in r.get("tags", []))]
    return rows


def log_notify(log_path: str | Path) -> Callable[[Entry], None]:
    """A local stand-in for the hosted notifier: append public publishes to a log."""
    def _notify(entry: Entry) -> None:
        p = Path(log_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(entry)) + "\n")
    return _notify
