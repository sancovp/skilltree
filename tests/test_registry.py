"""P5.2 tests: registry schema, the contribution gate, gated promotion."""
from __future__ import annotations

import json
from pathlib import Path

from skilltree import (
    load_registry,
    promote,
    registry_search,
    validate_contribution,
    validate_registry,
)

ROOT = {"name": "m", "parent": None, "entries": [
    {"name": "owned", "kind": "skill", "repo": "github:me/x", "trust": "verified",
     "provenance": {"by": "me"}},
]}


def _add(entry):
    head = json.loads(json.dumps(ROOT))
    head["entries"].append(entry)
    return head


def test_schema_valid_and_invalid():
    assert validate_registry(ROOT) == []
    bad = {"name": "m", "parent": None, "entries": [{"name": "x", "kind": "nope", "repo": "r"}]}
    assert any("kind" in e for e in validate_registry(bad))


def test_valid_contribution_adds_unverified():
    head = _add({"name": "new", "kind": "skill", "repo": "github:a/b", "trust": "unverified",
                 "provenance": {"by": "alice"}})
    assert validate_contribution(ROOT, head) == []


def test_contribution_cannot_self_promote():
    head = _add({"name": "new", "kind": "skill", "repo": "github:a/b", "trust": "verified",
                 "provenance": {"by": "alice"}})
    assert any("unverified" in e for e in validate_contribution(ROOT, head))


def test_contribution_needs_provenance():
    head = _add({"name": "new", "kind": "skill", "repo": "github:a/b", "trust": "unverified"})
    assert any("provenance" in e for e in validate_contribution(ROOT, head))


def test_contribution_cannot_tamper_others():
    # change an existing entry's trust
    head = json.loads(json.dumps(ROOT))
    head["entries"][0]["trust"] = "unverified"
    assert any("trust" in e for e in validate_contribution(ROOT, head))
    # remove an existing entry
    head2 = {"name": "m", "parent": None, "entries": []}
    assert any("removes" in e for e in validate_contribution(ROOT, head2))
    # re-parent / rename
    head3 = json.loads(json.dumps(ROOT)); head3["parent"] = "github:evil/x"
    assert any("parent" in e for e in validate_contribution(ROOT, head3))


def test_promote_is_the_gated_step(tmp_path: Path):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_add({"name": "new", "kind": "skill", "repo": "github:a/b",
                                    "trust": "unverified", "provenance": {"by": "alice"}})))
    entry = promote(reg, "new", to="verified", by="sancovp", now="2026-06-16T00:00:00")
    assert entry.trust == "verified"
    assert load_registry(reg)["entries"][-1]["provenance"]["promoted_by"] == "sancovp"


def test_search_trust_floor(tmp_path: Path):
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(_add({"name": "new", "kind": "skill", "repo": "github:a/b",
                                    "trust": "unverified", "provenance": {"by": "alice"}})))
    assert {e["name"] for e in registry_search(reg, min_trust="verified")} == {"owned"}
    assert {e["name"] for e in registry_search(reg, min_trust="unverified")} == {"owned", "new"}
