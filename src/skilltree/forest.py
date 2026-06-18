"""Make a SkillTree (or a forest of them) visible from the TOP — `~/.claude/skills`.

The top-level user `.claude/skills` is scanned in every session, but the scan is
non-recursive WITHIN a `.claude/skills` (a skill can't contain auto-loadable
sub-skills). So to surface a tree from the top you SYMLINK its entry skill dirs
into `~/.claude/skills`, and the `cat`-breadcrumbs carry you down from there.

  - single tree  → `link_tree`: symlink the root (and its first-layer branches) up
  - many trees   → `build_forest`: one forest-root skill that breadcrumbs to each
                   tree's root, symlinked up — a forest view over the top.
"""
from __future__ import annotations

from pathlib import Path

from .model import SkillTree, skill_name

_CRUMB = "- {name} ({kind}): Read `{path}`"     # the Read TOOL injects the layer, not `cat`


def _skill_dir(node_dir: Path, name: str) -> Path:
    return Path(node_dir) / ".claude" / "skills" / name


def _symlink(link: Path, target: Path) -> Path:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(Path(target).resolve(), target_is_directory=True)
    return link


def link_tree(tree_dir: str | Path, *, user_skills_dir: str | Path,
              manifest: str | Path | None = None,
              include_root: bool = True, branches: bool = True) -> list[Path]:
    """Symlink a single tree's entry points into the top-level user skills dir.

    The root gives the overview + breadcrumbs; the branches (root's direct
    children) are surfaced too so the first layer is reachable from the top.
    Deeper levels stay behind `cat` (progressive disclosure).
    """
    tree_dir = Path(tree_dir)
    tree = SkillTree.load(manifest or tree_dir / "skilltree.json")
    user = Path(user_skills_dir)
    links: list[Path] = []
    if include_root:
        rn = skill_name(tree.root)
        links.append(_symlink(user / rn, _skill_dir(tree_dir, rn)))
    if branches:
        for child in tree.root.children:
            cn = skill_name(child)
            links.append(_symlink(user / cn, _skill_dir(tree_dir / child.name, cn)))
    return links


def build_forest(name: str, members: list[str | Path], *, user_skills_dir: str | Path,
                 forest_dir: str | Path, description: str | None = None) -> Path:
    """Build a forest-root skill over several trees and symlink it to the top.

    `members` = tree dirs (each with a skilltree.json). The forest root's body
    breadcrumbs to each tree's root; one top-level entry, progressive descent.
    """
    fdir = _skill_dir(Path(forest_dir), name)
    fdir.mkdir(parents=True, exist_ok=True)
    crumbs, roots = [], []
    for tdir in members:
        tdir = Path(tdir)
        tree = SkillTree.load(tdir / "skilltree.json")
        rn = skill_name(tree.root)
        md = _skill_dir(tdir, rn) / "SKILL.md"
        crumbs.append(_CRUMB.format(name=rn, kind=tree.root.kind, path=md.resolve()))
        roots.append(rn)
    desc = description or f"Forest of {len(members)} skill tree(s): {', '.join(roots)}."
    body = (f"Forest **{name}** — {len(members)} skill tree(s). "
            "Pick one and **Read** (the Read tool) into its root to load it, then follow its "
            "breadcrumbs down (`cat` won't load it — only the Read tool does):\n\n" + "\n".join(crumbs))
    (fdir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n\n{body}\n", encoding="utf-8")
    return _symlink(Path(user_skills_dir) / name, fdir)


def list_links(user_skills_dir: str | Path) -> list[dict]:
    """List symlinks in the user skills dir and whether they still resolve."""
    user = Path(user_skills_dir)
    out: list[dict] = []
    if user.exists():
        for p in sorted(user.iterdir()):
            if p.is_symlink():
                out.append({"name": p.name, "target": str(p.readlink()), "resolves": p.exists()})
    return out


def unlink(user_skills_dir: str | Path, *names: str) -> list[str]:
    """Remove named symlinks (only if they are symlinks — never deletes real dirs)."""
    user = Path(user_skills_dir)
    removed: list[str] = []
    for n in names:
        p = user / n
        if p.is_symlink():
            p.unlink()
            removed.append(n)
    return removed
