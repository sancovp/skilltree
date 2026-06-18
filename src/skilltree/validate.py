"""Validate a materialized SkillTree (the `cat`-breadcrumb tree).

The auto-loader only loads the root and never follows the breadcrumbs, so nothing
guarantees the tree is traversable — this validator is that guarantee. It checks
the things the filesystem won't:

  - every node has a loadable SKILL.md (name + description frontmatter)
  - every non-leaf node's body has a Read breadcrumb for EACH of its children
  - every breadcrumb path actually resolves to a file (no dead ends)
  - sibling names are unique (their dirs collide otherwise)

A non-empty error list is a kill-criterion: someone walking the tree hits a dead
end the platform would never warn about.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .model import KINDS, SkillTree, TreeNode, skill_name

# a breadcrumb is `- <name> (<kind>): Read `<abspath>`` — match the backticked SKILL.md path
# (verb-agnostic, so it survives wording tweaks; the verb is the Read tool, never `cat`)
_CRUMB_RE = re.compile(r"`([^`]+/SKILL\.md)`")


@dataclass
class Violation:
    severity: str        # "error" | "warning"
    where: str
    message: str


def _has_frontmatter(skill_md: Path) -> bool:
    if not skill_md.is_file():
        return False
    txt = skill_md.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"^\s*name:\s*\S", txt, re.M) and re.search(r"^\s*description:\s*\S", txt, re.M))


def _skill_md(node_dir: Path, name: str) -> Path:
    return node_dir / ".claude" / "skills" / name / "SKILL.md"


def _walk(node: TreeNode, node_dir: Path, out: list[Violation]) -> None:
    skill_md = _skill_md(node_dir, skill_name(node))
    if node.kind not in KINDS:
        out.append(Violation("warning", node.name, f"unknown kind {node.kind!r}"))
    if not skill_md.is_file():
        out.append(Violation("error", node.name, f"missing SKILL.md at {skill_md}"))
        return
    if not _has_frontmatter(skill_md):
        out.append(Violation("error", node.name, "SKILL.md lacks name/description frontmatter (won't auto-load)"))

    child_names = [c.name for c in node.children]
    for d in {n for n in child_names if child_names.count(n) > 1}:
        out.append(Violation("error", node.name, f"duplicate child name {d!r} (sibling dirs collide)"))

    if node.children:
        text = skill_md.read_text(encoding="utf-8")
        found = {Path(m).resolve() for m in _CRUMB_RE.findall(text)}
        expected = {_skill_md(node_dir / c.name, skill_name(c)).resolve() for c in node.children}
        for missing in expected - found:
            out.append(Violation("error", node.name, f"no Read breadcrumb for child → {missing}"))
        for p in found:
            if not Path(p).is_file():
                out.append(Violation("error", node.name, f"dead breadcrumb: `{p}` does not resolve"))
            elif p not in expected:
                out.append(Violation("warning", node.name, f"breadcrumb `{p}` is not a declared child"))

    for child in node.children:
        _walk(child, node_dir / child.name, out)


def validate(root: str | Path, tree: SkillTree | None = None) -> list[Violation]:
    root = Path(root)
    if tree is None:
        manifest = root / "skilltree.json"
        if not manifest.is_file():
            return [Violation("error", str(root), "no skilltree.json manifest found")]
        tree = SkillTree.load(manifest)
    out: list[Violation] = []
    _walk(tree.root, root, out)          # root node's dir IS the tree root
    return out


def is_valid(root: str | Path, tree: SkillTree | None = None) -> bool:
    return not any(v.severity == "error" for v in validate(root, tree))
