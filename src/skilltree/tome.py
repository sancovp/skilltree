"""tome.py — the SkillVolume/SkillTome bind ops (fold a framework into a volume).

A **SkillVolume** is a SkillTree branch that HOLDS frameworks: its node carries
`frameworks` rows in the manifest, rendered as the `## Frameworks` pointer-table
(see model.tome_table). A **SkillTome** is the overall corpus — the set of volumes
+ everything made with them. ("nomicon" is the legacy alias for both.)

`fold(framework_dir, into=...)` is the bind operator: register ONE framework
(a chapter — its skill dir) as a row on a volume node. Idempotent — one row per
framework name; re-folding the same framework updates its row in place. The
manifest is the source of truth; the node's SKILL.md table is regenerated from it
surgically (only that node is rewritten — never a destructive re-materialize).

The flat deployment of a folded volume is `forest.project(policy="flat")`.
"""
from __future__ import annotations

from pathlib import Path

from .model import SkillTree, find_node, skill_name


def fold(framework_dir: str | Path, *, into: str, tree_root: str | Path,
         what_for: str | None = None, name: str | None = None) -> dict:
    """Fold a framework's skill dir into a volume node's tome table — one row,
    idempotent by row name. Returns a report dict ({"ok": False, "error": ...} on
    a bad target — no partial writes happen in that case).

    framework_dir  the framework's skill dir (must contain SKILL.md)
    into           the volume node, by name or coordinate
    tree_root      the materialized tree root (holds skilltree.json)
    what_for       the row's purpose text (default: the framework's description)
    name           the row name (default: the framework's frontmatter name, else dir name)
    """
    from .cohere import _front, _rewrite_node_md   # frontmatter parse + surgical rewrite

    tree_root = Path(tree_root)
    manifest = tree_root / "skilltree.json"
    if not manifest.is_file():
        return {"ok": False, "error": f"no skilltree.json manifest at {tree_root}"}
    fdir = Path(framework_dir)
    smd = fdir / "SKILL.md"
    if not smd.is_file():
        return {"ok": False, "error": f"framework dir has no SKILL.md: {fdir}"}

    tree = SkillTree.load(manifest)
    hit = find_node(tree.root, into)
    if hit is None:
        return {"ok": False, "error": f"no node named/coord {into!r} in {manifest}"}
    node, path = hit

    front = _front(smd)
    row_name = name or front.get("name") or fdir.name
    row = {"name": row_name,
           "what_for": what_for or front.get("description", ""),
           "skill_path": str(smd.resolve())}
    updated = False
    for i, r in enumerate(node.frameworks):
        if r.get("name") == row_name:       # idempotent: one row per framework
            node.frameworks[i] = row
            updated = True
            break
    if not updated:
        node.frameworks.append(row)

    tree.save(manifest)

    # Surgical in-place rewrite of ONLY the folded node's SKILL.md (regenerates its
    # generated tail — table included — from the model; hand-written body preserved).
    node_dir = tree_root
    for nm in path[1:]:
        node_dir = node_dir / nm
    _rewrite_node_md(node_dir / ".claude" / "skills" / skill_name(node) / "SKILL.md",
                     node, node_dir)

    return {"ok": True, "node": node.name, "coord": node.coord, "row": row,
            "updated": updated, "rows": len(node.frameworks)}
