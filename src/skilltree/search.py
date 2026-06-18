"""The `search` arm — coordinate-scoped lexical search over the skill corpus.

v1 (evidence-driven, see .claude/rules + the research): SQLite **FTS5 / BM25** over
the skill files, with **coordinate-scoped subtree filtering** — rank within any
coord-rooted region of the tree (`scope_coord="0.1"` → only `0.1` and its
descendants). For a small corpus of short, keyword-dense skill docs, BM25 is
enough; the differentiated capability is the subtree scoping (the coordinate is
the address AND the search scope).

A dense/vector layer fused via RRF is a LATER, evidence-driven upgrade — add it
only when logged BM25 misses are semantic (synonym/paraphrase), not lexical.
MCTS-style tree search is for skill *composition* (SCCC), not lookup.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_COORD_NAME = re.compile(r"^([0-9][0-9.]*)-(.+)$")
_FTS_TERMS = re.compile(r"\w+")


def _read_skill(md: Path) -> tuple[str, str, str, str, str, int]:
    txt = md.read_text(encoding="utf-8", errors="replace")
    nm = re.search(r"^\s*name:\s*(.+?)\s*$", txt, re.M)
    ds = re.search(r"^\s*description:\s*(.+?)\s*$", txt, re.M)
    gl = re.search(r"^\s*glyphs:\s*(.+?)\s*$", txt, re.M)
    vs = re.search(r"^\s*version:\s*(\d+)", txt, re.M)
    name = nm.group(1).strip() if nm else md.parent.name
    desc = ds.group(1).strip() if ds else ""
    glyphs = gl.group(1).strip() if gl else ""
    version = int(vs.group(1)) if vs else 1
    body = txt.split("---", 2)[-1].strip() if txt.lstrip().startswith("---") else txt.strip()
    m = _COORD_NAME.match(name)
    coord = m.group(1) if m else ""
    return coord, name, desc, body, glyphs, version


def _logical(name: str) -> str:
    """The stable logical identity of a skill: drop the coord prefix and any `-v<N>` version suffix."""
    m = _COORD_NAME.match(name)
    base = m.group(2) if m else name
    return re.sub(r"-v\d+$", "", base)


def build_index(root_dir: str | Path, db_path: str = ":memory:",
                vocab=None) -> sqlite3.Connection:
    """Index every SKILL.md under root_dir into an FTS5 table. Returns the connection.

    GlyphSteer integration: if `vocab` (a glyphsteer.Vocabulary) is given, each skill's
    `glyphs:` frontmatter code is rendered to ASCII sentinel **tags** (indexed for
    faceting — FTS5 drops the emoji itself); the raw glyph code is kept UNINDEXED for
    display. `vocab=None` ⇒ original behaviour, no glyph columns used.
    """
    con = sqlite3.connect(db_path)
    con.execute("CREATE VIRTUAL TABLE skills USING fts5(name, description, body, tags, "
                "coord UNINDEXED, path UNINDEXED, glyphs UNINDEXED, version UNINDEXED)")
    rows = []
    for md in Path(root_dir).rglob("SKILL.md"):
        coord, name, desc, body, glyphs, version = _read_skill(md)
        tags = " ".join(vocab.code_tags(glyphs)) if (vocab and glyphs) else ""
        rows.append((name, desc, body, tags, coord, str(md), glyphs, version))
    con.executemany("INSERT INTO skills(name, description, body, tags, coord, path, glyphs, version) "
                    "VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return con


def _fts_query(q: str) -> str:
    terms = _FTS_TERMS.findall(q)
    return " OR ".join(terms) if terms else q


def search(con: sqlite3.Connection, query: str, *, scope_coord: str | None = None,
           facet: str | None = None, vocab=None, limit: int = 10,
           newest_only: bool = False) -> list[dict]:
    """BM25-ranked search, optionally scoped to a coordinate subtree and/or faceted by a
    GlyphSteer glyph (`facet`, resolved to its ASCII sentinel tag via `vocab`).
    `newest_only=True` forwards only the **newest `version` per logical skill** (history kept on disk,
    but search returns the latest) — the self-expansion/freshness routing."""
    sql = ("SELECT name, coord, description, path, glyphs, version, bm25(skills) AS score "
           "FROM skills WHERE skills MATCH ?")
    params: list = [_fts_query(query)]
    if scope_coord:
        sql += " AND (coord = ? OR coord LIKE ?)"
        params += [scope_coord, f"{scope_coord}.%"]
    if facet:
        tag = (vocab.tag_for(facet) if vocab else None) or facet
        sql += " AND tags MATCH ?"
        params.append(tag)
    sql += " ORDER BY score"               # bm25(): lower = better
    hits = [{"name": r[0], "coord": r[1], "description": r[2], "path": r[3], "glyphs": r[4],
             "version": int(r[5]) if str(r[5]).isdigit() else 1, "score": r[6]}
            for r in con.execute(sql, params)]
    if newest_only:
        best: dict[str, dict] = {}
        for h in hits:                     # keep the highest version per logical name
            k = _logical(h["name"])
            if k not in best or h["version"] > best[k]["version"]:
                best[k] = h
        hits = sorted(best.values(), key=lambda h: h["score"])
    return hits[:limit]


def search_tree(root_dir: str | Path, query: str, *, scope_coord: str | None = None,
                facet: str | None = None, vocab=None, limit: int = 10,
                newest_only: bool = False) -> list[dict]:
    """Convenience: index a tree dir and search it in one call."""
    return search(build_index(root_dir, vocab=vocab), query, scope_coord=scope_coord,
                  facet=facet, vocab=vocab, limit=limit, newest_only=newest_only)
