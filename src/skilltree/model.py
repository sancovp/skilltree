"""SkillTree model — a tree of skill dirs wired by LINKS, not nesting.

Every node is a skill dir (`<name>/SKILL.md`) of any type (ac/cor/sc/skill).
Edges are links: each node lives in its OWN `.claude/skills/` root, and a node's
direct children are symlinked into that root. Auto-load reaches a root + its
direct children only — never deeper (a skill dir won't auto-load a nested
`.claude`). To descend, you REDIRECT the active skills root to the child's root.

Because the platform won't traverse this, the tree's integrity is not guaranteed
by the filesystem — it must be validated programmatically (see validate.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

KINDS = ("ac", "cor", "sc", "skill")


@dataclass
class TreeNode:
    name: str                       # slug; also the tree-path dir name
    kind: str = "skill"             # ac | cor | sc | skill
    skill_src: str | None = None    # existing `<name>/SKILL.md` dir to carry as content (else a stub)
    description: str | None = None   # SKILL.md description (so it auto-loads / is searchable)
    coord: str | None = None         # hierarchical address (e.g. "0.1.2"); set by assign_coords
    children: list["TreeNode"] = field(default_factory=list)
    # tome pointer-table rows (the SkillVolume binding): each row registers a framework
    # this node HOLDS — {"name", "what_for", "skill_path" (abs path to its SKILL.md)}.
    # Rendered as the `## Frameworks` table by tome_table(); added by tome.fold().
    frameworks: list[dict] = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def edges(self):
        for child in self.children:
            yield (self.name, child.name)
            yield from child.edges()


def skill_name(node: "TreeNode") -> str:
    """The skill's identity (frontmatter name + skill-dir name).

    With a coord, it is `<coord>-<name>` — so the flat skills list is coord-sorted,
    reveals the tree, and each node is addressable by its coordinate. The tree-PATH
    dir stays the plain `name`; only the skill identity carries the coord.
    """
    return f"{node.coord}-{node.name}" if node.coord else node.name


def compose_summary(node: "TreeNode", *, full: bool = False) -> str:
    """A DETERMINISTIC semantic summary of an index (branch) node — a template
    filled with its coordinate, children, and reachable descendants.

    This is the RAPTOR "internal nodes carry a summary" retrieval-win, gotten for
    free (no LLM): the branch's body becomes dense with its subtree's vocabulary,
    so a query about any descendant matches the branch that leads to it. `full`
    adds the flattened reachable-leaf list (for the indexed body); the short form
    (for the description) lists just the immediate children.
    """
    kids = ", ".join(f"{c.name} ({c.kind})" for c in node.children) or "(none)"
    short = f"opens to {len(node.children)} branch(es): {kids}"
    if not full:
        return short
    reachable = [d.name for d in node.walk() if d is not node]
    return (f"[{node.coord or '?'}] {node.name} — a {node.kind} index node; {short}. "
            f"Reachable below: {', '.join(reachable)}.")


# A breadcrumb names its child's SKILL.md one of two ways. PORTABLE (the default): relative to
# the node's folder — the folder that holds this SKILL.md's `.claude/` — so a tree carries no
# machine's path and validates wherever it is copied. LOCALIZED: absolute, for a tree that is
# installed or projected (read through a symlink, where only an absolute path resolves).
PORTABLE_NOTE = ("Each path below is relative to this node's folder — the folder that holds this "
                 "file's `.claude/` — so join it to that folder before you Read it.")


def crumb_path(child_md: Path, node_dir: Path, *, localize: bool = False) -> str:
    """The path a breadcrumb names (see PORTABLE_NOTE)."""
    if localize:
        return str(Path(child_md).resolve())
    return Path(os.path.relpath(os.path.abspath(child_md), os.path.abspath(node_dir))).as_posix()


TOME_HEADING = "## Frameworks"


def tome_table(node: "TreeNode") -> str:
    """Render a node's tome pointer-table (the `## Frameworks` registry) from the model.

    The table is GENERATED — the manifest's `frameworks` rows are the source of truth,
    and both materialize and cohere's in-place rewrite re-emit it (so a re-cohere can
    never wipe or drift a folded row). The 'Framework skill' cell is `name (<abs path
    to SKILL.md>)` — the exact shape the flat projector (`project(policy="flat")`, née
    nomicon-atomize) parses. Columns grow Plugin/Chapter in Move 2.
    """
    lines = [TOME_HEADING, "",
             "| Framework | What it's for | Framework skill |",
             "|---|---|---|"]
    for r in node.frameworks:
        lines.append(f"| {r['name']} | {r.get('what_for', '')} | {r['name']} ({r['skill_path']}) |")
    return "\n".join(lines)


def find_node(root: "TreeNode", selector: str) -> tuple["TreeNode", list[str]] | None:
    """Locate a node by NAME or COORD; returns (node, tree-path names root→node)."""
    def walk(n: "TreeNode", path: list[str]):
        if n.name == selector or (n.coord and n.coord == selector):
            return n, path
        for c in n.children:
            hit = walk(c, path + [c.name])
            if hit:
                return hit
        return None
    return walk(root, [root.name])


def assign_coords(root: "TreeNode", base: str = "0") -> "TreeNode":
    """Give every node a hierarchical coordinate: root=base, child i (1-based)=parent.i."""
    def walk(n: "TreeNode", coord: str) -> None:
        n.coord = coord
        for i, child in enumerate(n.children, 1):
            walk(child, f"{coord}.{i}")
    walk(root, base)
    return root


@dataclass
class SkillTree:
    root: TreeNode

    # ---- manifest (source of truth for validation) ----
    def to_manifest(self) -> dict:
        def enc(n: TreeNode) -> dict:
            return {"name": n.name, "kind": n.kind, "skill_src": n.skill_src,
                    "description": n.description, "coord": n.coord,
                    "frameworks": [dict(r) for r in n.frameworks],
                    "children": [enc(c) for c in n.children]}
        return {"skilltree": enc(self.root)}

    @staticmethod
    def from_manifest(data: dict) -> "SkillTree":
        def dec(d: dict) -> TreeNode:
            return TreeNode(name=d["name"], kind=d.get("kind", "skill"),
                            skill_src=d.get("skill_src"), description=d.get("description"),
                            coord=d.get("coord"),
                            frameworks=[dict(r) for r in d.get("frameworks", [])],
                            children=[dec(c) for c in d.get("children", [])])
        return SkillTree(dec(data["skilltree"]))

    def save(self, path: str | Path) -> Path:
        """Write the manifest. Every `skill_src` is stored RELATIVE to the manifest's own
        folder, so a committed manifest names no machine's path; `load` resolves it back."""
        p = Path(path)
        data = self.to_manifest()
        base = os.path.abspath(p.parent)

        def rel(d: dict) -> None:
            s = d.get("skill_src")
            if s and os.path.isabs(s):
                d["skill_src"] = Path(os.path.relpath(os.path.abspath(s), base)).as_posix()
            for c in d.get("children", []):
                rel(c)
        rel(data["skilltree"])
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return p

    @staticmethod
    def load(path: str | Path) -> "SkillTree":
        """Read a manifest; a relative `skill_src` resolves against the manifest's folder."""
        p = Path(path)
        tree = SkillTree.from_manifest(json.loads(p.read_text(encoding="utf-8")))
        base = os.path.abspath(p.parent)
        for n in tree.root.walk():
            if n.skill_src and not os.path.isabs(n.skill_src):
                n.skill_src = os.path.normpath(os.path.join(base, n.skill_src))
        return tree

    def nodes(self) -> list[TreeNode]:
        return list(self.root.walk())

    def edges(self) -> list[tuple[str, str]]:
        return list(self.root.edges())
