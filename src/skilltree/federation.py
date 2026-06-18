"""P5.4 — walk the federation: a tree of marketplaces under a root.

A child marketplace joins by contributing a `registry`-kind entry to its parent's
registry.json (pointing at the child's own registry.json). Federation is then a
walk: from the root registry, resolve each `registry` entry to the child's
registry and recurse — a tree of marketplaces mirroring the tree of repos.

`resolve` is pluggable so this works offline: it maps a `registry` entry to a
registry dict (a local map for tests; a fetch-by-repo-ref for the real network).
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Callable

from .registry import load_registry, validate_registry

Resolver = Callable[[dict], "dict | None"]


def local_resolver(name_to_registry: dict[str, dict]) -> Resolver:
    """Resolve a `registry` entry to a child registry from an in-memory/local map."""
    def _resolve(entry: dict) -> dict | None:
        target = name_to_registry.get(entry["name"]) or name_to_registry.get(entry.get("repo", ""))
        if isinstance(target, (str, Path)):
            return load_registry(target)
        return target
    return _resolve


def _children(registry: dict) -> list[dict]:
    return [e for e in registry.get("entries", []) if e.get("kind") == "registry"]


def walk_federation(registry: dict, resolve: Resolver, *, _seen: frozenset[str] | None = None) -> dict:
    """Return the nested federation tree rooted at `registry`."""
    _seen = _seen or frozenset()
    name = registry.get("name")
    node = {
        "name": name,
        "entries": [e for e in registry.get("entries", []) if e.get("kind") != "registry"],
        "children": [],
    }
    if name in _seen:                       # cycle guard
        node["cycle"] = True
        return node
    seen = _seen | {name}
    for entry in _children(registry):
        child = resolve(entry)
        if child is None:
            node["children"].append({"name": entry["name"], "unresolved": True})
        else:
            node["children"].append(walk_federation(child, resolve, _seen=seen))
    return node


def flatten_federation(registry: dict, resolve: Resolver) -> list[dict]:
    """Every leaf entry across the federation, tagged with the registry path it came through."""
    out: list[dict] = []

    def rec(node: dict, path: tuple[str, ...]) -> None:
        here = path + (node["name"],)
        for e in node.get("entries", []):
            out.append({**e, "_path": list(here)})
        for c in node.get("children", []):
            if not c.get("unresolved") and not c.get("cycle"):
                rec(c, here)
    rec(walk_federation(registry, resolve), ())
    return out


def validate_federation(registry: dict, resolve: Resolver) -> list[str]:
    """Check the federation: child schemas valid, parent backrefs consistent, no cycles."""
    errs: list[str] = []

    def rec(reg: dict, seen: frozenset[str]) -> None:
        errs.extend(f"{reg.get('name')}: {e}" for e in validate_registry(reg))
        if reg.get("name") in seen:
            errs.append(f"federation cycle at {reg.get('name')!r}")
            return
        s = seen | {reg.get("name")}
        for entry in _children(reg):
            child = resolve(entry)
            if child is None:
                errs.append(f"{reg.get('name')}: unresolved child registry {entry['name']!r}")
                continue
            if child.get("parent") not in (None, reg.get("name")) and "github" not in str(child.get("parent", "")):
                errs.append(f"{child.get('name')!r}: parent backref {child.get('parent')!r} "
                            f"does not match {reg.get('name')!r}")
            rec(child, s)
    rec(registry, frozenset())
    return errs


def register_child(parent_path: str | Path, name: str, repo: str, *,
                   manifest: str = "registry.json", by: str = "maintainer",
                   now: str | None = None) -> dict:
    """Add a `registry`-kind child to a parent registry (federation link, unverified)."""
    p = Path(parent_path)
    data = load_registry(p)
    data.setdefault("entries", []).append({
        "name": name, "kind": "registry", "repo": repo, "manifest": manifest,
        "version": "0.1.0", "trust": "unverified",
        "provenance": {"by": by, "at": now or _dt.datetime.now().isoformat(timespec="seconds")},
    })
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data
