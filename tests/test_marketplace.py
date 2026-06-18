"""Marketplace tests: programmatic publish, opt-in public, notify hook, search."""
from __future__ import annotations

from pathlib import Path

from skilltree.marketplace import log_notify, publish, search


def test_publish_and_search(tmp_path: Path):
    reg = tmp_path / "registry.json"
    publish(reg, "debug-attn", tmp_path / "skills" / "debug-attn", kind="skill", tags=["debug"])
    publish(reg, "cc-master", tmp_path / "repo", kind="exchange", public=True)
    assert len(search(reg)) == 2
    assert [r["name"] for r in search(reg, "debug")] == ["debug-attn"]
    assert [r["name"] for r in search(reg, public_only=True)] == ["cc-master"]


def test_upsert_by_name(tmp_path: Path):
    reg = tmp_path / "registry.json"
    publish(reg, "x", "/a", version="0.1.0")
    publish(reg, "x", "/a", version="0.2.0")          # same name → updated, not duplicated
    rows = search(reg)
    assert len(rows) == 1 and rows[0]["version"] == "0.2.0"


def test_notify_fires_only_when_public(tmp_path: Path):
    reg = tmp_path / "registry.json"
    log = tmp_path / "notify.log"
    notify = log_notify(log)
    publish(reg, "private-one", "/p", public=False, notify=notify)
    assert not log.exists()                            # private → no notify
    publish(reg, "public-one", "/q", public=True, notify=notify)
    assert log.exists() and "public-one" in log.read_text()   # public → notified ("grows")
