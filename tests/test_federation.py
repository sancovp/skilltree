"""P5.4 tests: walking a federation of marketplaces, with cycle/backref checks."""
from __future__ import annotations

from skilltree import (
    flatten_federation,
    local_resolver,
    validate_federation,
    walk_federation,
)


def _reg(name, parent, entries):
    return {"name": name, "parent": parent, "entries": entries}


def _skill(name, by="x"):
    return {"name": name, "kind": "skill", "repo": f"github:{by}/{name}",
            "trust": "verified", "provenance": {"by": by}}


def _child_ref(name):
    return {"name": name, "kind": "registry", "repo": f"github:o/{name}",
            "trust": "verified", "provenance": {"by": "o"}}


def _world():
    root = _reg("root", None, [_skill("root-skill"), _child_ref("alpha"), _child_ref("beta")])
    alpha = _reg("alpha", "root", [_skill("alpha-skill"), _child_ref("gamma")])
    beta = _reg("beta", "root", [_skill("beta-skill")])
    gamma = _reg("gamma", "alpha", [_skill("gamma-skill")])
    resolve = local_resolver({"alpha": alpha, "beta": beta, "gamma": gamma})
    return root, resolve


def test_walk_nests_the_federation():
    root, resolve = _world()
    tree = walk_federation(root, resolve)
    assert tree["name"] == "root"
    kids = {c["name"] for c in tree["children"]}
    assert kids == {"alpha", "beta"}
    alpha = next(c for c in tree["children"] if c["name"] == "alpha")
    assert {c["name"] for c in alpha["children"]} == {"gamma"}


def test_flatten_tags_each_entry_with_its_path():
    root, resolve = _world()
    flat = {e["name"]: e["_path"] for e in flatten_federation(root, resolve)}
    assert flat["gamma-skill"] == ["root", "alpha", "gamma"]
    assert flat["beta-skill"] == ["root", "beta"]


def test_unresolved_child_is_flagged():
    root = _reg("root", None, [_child_ref("missing")])
    resolve = local_resolver({})                 # nothing resolves
    tree = walk_federation(root, resolve)
    assert tree["children"][0]["unresolved"]
    assert any("unresolved" in e for e in validate_federation(root, resolve))


def test_cycle_is_caught():
    a = _reg("a", None, [_child_ref("b")])
    b = _reg("b", "a", [_child_ref("a")])         # b points back to a → cycle
    resolve = local_resolver({"a": a, "b": b})
    assert any("cycle" in e for e in validate_federation(a, resolve))


def test_validate_federation_clean_world():
    root, resolve = _world()
    assert validate_federation(root, resolve) == []
