"""P5.2 — the marketplace as a git repo: registry.json + a contribution gate.

The registry is DATA (pointers), never code we run. A contribution is a PR that
ADDS entries — and the gate enforces the locked policy:

  - new entries must land `unverified` (promotion is maintainer-only)
  - contributions may not change another entry's trust, remove others' entries,
    or rename/re-parent the registry
  - every entry carries provenance

`promote()` is the separate, maintainer-only step that flips trust upward. This
is "validate → queue → gated promote" — no auto-merge of agent-loadable content.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import datetime as _dt
import json
from pathlib import Path
from typing import Any

KINDS = ("skill", "tree", "exchange", "mcp", "registry")   # `registry` = a federated child marketplace
TRUST = ("unverified", "verified", "featured")
_REQUIRED = ("name", "kind", "repo")


@dataclass
class Entry:
    name: str
    kind: str
    repo: str
    manifest: str = ""
    version: str = "0.1.0"
    trust: str = "unverified"
    provenance: dict = field(default_factory=dict)


def load_registry(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _by_name(data: dict) -> dict[str, dict]:
    return {e["name"]: e for e in data.get("entries", [])}


def validate_registry(data: dict) -> list[str]:
    """Schema check on a registry document."""
    errs: list[str] = []
    if not isinstance(data.get("name"), str):
        errs.append("registry: missing string `name`")
    if "parent" not in data:
        errs.append("registry: missing `parent` (use null at the root)")
    if not isinstance(data.get("entries"), list):
        errs.append("registry: `entries` must be a list")
        return errs
    seen: set[str] = set()
    for i, e in enumerate(data["entries"]):
        tag = e.get("name", f"#{i}")
        for f in _REQUIRED:
            if not e.get(f):
                errs.append(f"entry {tag}: missing `{f}`")
        if e.get("kind") not in KINDS:
            errs.append(f"entry {tag}: kind must be one of {KINDS}")
        if e.get("trust", "unverified") not in TRUST:
            errs.append(f"entry {tag}: trust must be one of {TRUST}")
        if e.get("name") in seen:
            errs.append(f"entry {tag}: duplicate name")
        seen.add(e.get("name"))
    return errs


def validate_contribution(base: dict, head: dict, *, actor: str | None = None) -> list[str]:
    """Gate a PR's registry change. Empty list = a valid (queued, unverified) contribution."""
    errs = validate_registry(head)
    if errs:
        return errs
    if head.get("name") != base.get("name"):
        errs.append("contribution may not rename the registry")
    if head.get("parent") != base.get("parent"):
        errs.append("contribution may not change the registry parent")
    b, h = _by_name(base), _by_name(head)
    for name in h.keys() - b.keys():                      # ADDED
        e = h[name]
        if e.get("trust", "unverified") != "unverified":
            errs.append(f"new entry {name!r} must be `unverified` (promotion is maintainer-only)")
        if not (e.get("provenance") or {}).get("by"):
            errs.append(f"new entry {name!r} must carry provenance.by")
    for name in b.keys() - h.keys():                      # REMOVED
        errs.append(f"contribution removes existing entry {name!r} (maintainer-only)")
    for name in b.keys() & h.keys():                      # MODIFIED
        if h[name].get("trust") != b[name].get("trust"):
            errs.append(f"contribution changes trust of {name!r} (maintainer-only — use promote)")
    return errs


def promote(path: str | Path, name: str, *, to: str = "verified", by: str | None = None,
            now: str | None = None) -> Entry:
    """Maintainer-only: flip an entry's trust. Direct (not via PR)."""
    if to not in TRUST:
        raise ValueError(f"trust must be one of {TRUST}")
    p = Path(path)
    data = load_registry(p)
    for e in data.get("entries", []):
        if e["name"] == name:
            e["trust"] = to
            e.setdefault("provenance", {})["promoted_by"] = by or "maintainer"
            e["provenance"]["promoted_at"] = now or _dt.datetime.now().isoformat(timespec="seconds")
            p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return Entry(**{k: e.get(k) for k in ("name", "kind", "repo", "manifest", "version", "trust", "provenance")})
    raise KeyError(f"no entry named {name!r}")


def search(path: str | Path, query: str | None = None, *, min_trust: str = "unverified") -> list[dict]:
    """Consumer view with a trust floor."""
    floor = TRUST.index(min_trust)
    rows = [e for e in load_registry(path).get("entries", []) if TRUST.index(e.get("trust", "unverified")) >= floor]
    if query:
        q = query.lower()
        rows = [e for e in rows if q in e["name"].lower()]
    return rows
