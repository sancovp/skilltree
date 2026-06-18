"""Materialize a SkillTree as nested dirs wired by `cat`-breadcrumbs.

The auto-loader only ever loads the ROOT (it won't descend a nested `.claude`).
So each node's SKILL.md body carries the `cat` commands that tell you how to read
its children — the breadcrumb links. The tree is nested dirs; traversal is manual
`cat` following the breadcrumbs. Layout for a node N with children C1..Ck:

    <N_dir>/.claude/skills/<N>/SKILL.md          # N's skill + `cat` links to each child
    <N_dir>/<C1>/.claude/skills/<C1>/SKILL.md     # child dir is a SIBLING of N's .claude
    <N_dir>/<C2>/...

The root node's dir IS the tree root; root skill at <root>/.claude/skills/<root>/.
Leaves carry the actual skill content (from skill_src); no further breadcrumbs.
"""
from __future__ import annotations

from pathlib import Path
import shutil

from .model import SkillTree, TreeNode, assign_coords, compose_summary, skill_name

# A breadcrumb line is parseable by validate.py: `- <name> (<kind>): Read `<abspath>``
# The verb is **Read** (the Read tool), NOT `cat`: only the Read tool injects a dir's
# .claude layer — a Bash `cat` reads the bytes but loads nothing (verified 2026-06-18).
_CRUMB = "- {name} ({kind}): Read `{path}`"


def node_skill_md(node_dir: Path, node_name: str) -> Path:
    return node_dir / ".claude" / "skills" / node_name / "SKILL.md"


def _front(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body.rstrip()}\n"


def _write_node(node: TreeNode, node_dir: Path, root: Path) -> None:
    sname = skill_name(node)                      # coord-prefixed identity (or plain name)
    skill_md = node_skill_md(node_dir, sname)
    skill_md.parent.mkdir(parents=True, exist_ok=True)

    # base body: the node's own skill content (from src) or a stub
    if node.skill_src and (Path(node.skill_src) / "SKILL.md").exists():
        src = (Path(node.skill_src) / "SKILL.md").read_text(encoding="utf-8")
        # strip frontmatter from the source body; we re-emit our own
        base = src.split("---", 2)[-1].strip() if src.lstrip().startswith("---") else src.strip()
        desc = node.description or f"{node.kind} node {node.name}"
    else:
        base = f"SkillTree {node.kind} node `{node.name}`."
        desc = node.description or f"{node.kind} node {node.name} in a SkillTree."
    if node.children:
        # index (branch) node: a deterministic subtree summary makes it retrievable
        # by any descendant's terms (the RAPTOR win, no LLM).
        if not node.description:
            desc = compose_summary(node, full=False)
        summary = compose_summary(node, full=True)
        crumbs = [_CRUMB.format(name=skill_name(c), kind=c.kind,
                                path=node_skill_md(node_dir / c.name, skill_name(c)).resolve())
                  for c in node.children]
        body = (f"{base}\n\n## Index summary\n{summary}\n\n"
                f"## Descend — the next layer ({len(node.children)})\n"
                "Only this layer is loaded now. To descend, use the **Read tool** on a child "
                "below — that injects the child's layer (its persona + skills). A Bash `cat` "
                "reads the bytes but loads nothing; you must use the Read tool:\n\n"
                + "\n".join(crumbs))
    else:
        body = base + "\n\n_(leaf — this is an actual skill.)_"

    if node.coord:
        desc = f"[{node.coord}] {desc}"

    skill_md.write_text(_front(sname, desc, body), encoding="utf-8")

    # recurse: each child's dir is a sibling of this node's .claude (tree-path uses plain name)
    for child in node.children:
        _write_node(child, node_dir / child.name, root)


def materialize(tree: SkillTree, root: str | Path, *, overwrite: bool = True,
                coords: bool = False, base: str = "0") -> Path:
    root = Path(root)
    if coords:
        assign_coords(tree.root, base)            # address every node before writing
    if overwrite and root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    _write_node(tree.root, root, root)          # root node's dir IS the tree root
    tree.save(root / "skilltree.json")
    return root
