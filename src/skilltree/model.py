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
                    "children": [enc(c) for c in n.children]}
        return {"skilltree": enc(self.root)}

    @staticmethod
    def from_manifest(data: dict) -> "SkillTree":
        def dec(d: dict) -> TreeNode:
            return TreeNode(name=d["name"], kind=d.get("kind", "skill"),
                            skill_src=d.get("skill_src"), description=d.get("description"),
                            coord=d.get("coord"),
                            children=[dec(c) for c in d.get("children", [])])
        return SkillTree(dec(data["skilltree"]))

    def save(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(json.dumps(self.to_manifest(), indent=2), encoding="utf-8")
        return p

    @staticmethod
    def load(path: str | Path) -> "SkillTree":
        return SkillTree.from_manifest(json.loads(Path(path).read_text(encoding="utf-8")))

    def nodes(self) -> list[TreeNode]:
        return list(self.root.walk())

    def edges(self) -> list[tuple[str, str]]:
        return list(self.root.edges())
