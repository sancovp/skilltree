"""Make a SkillTree (or a forest of them) visible from the TOP — `~/.claude/skills`.

The top-level user `.claude/skills` is scanned in every session, but the scan is
non-recursive WITHIN a `.claude/skills` (a skill can't contain auto-loadable
sub-skills). So to surface a tree from the top you SYMLINK its entry skill dirs
into `~/.claude/skills`, and the `cat`-breadcrumbs carry you down from there.

ONE projector, two policies (`project`):
  - **progressive** → symlink the root (and its first-layer branches) up; deeper
    levels stay behind Read-breadcrumbs (progressive disclosure). `link_tree` is
    the thin compatibility wrapper.
  - **flat** → project a volume node's tome-table rows (its held frameworks) +
    the holder node itself as top-level skill dirs, so agents auto-discover every
    framework (the nomicon-atomize semantics: the organized tree stays the source
    of truth; the flat dir is only symlinks — edits propagate, nothing duplicates).
  - many trees → `build_forest`: one forest-root skill that breadcrumbs to each
    tree's root, symlinked up — a forest view over the top.
"""
from __future__ import annotations

import os
from pathlib import Path

from .model import SkillTree, find_node, skill_name

_CRUMB = "- {name} ({kind}): Read `{path}`"     # the Read TOOL injects the layer, not `cat`


def _skill_dir(node_dir: Path, name: str) -> Path:
    return Path(node_dir) / ".claude" / "skills" / name


def _symlink(link: Path, target: Path, *, relative: bool = False) -> Path | None:
    """Idempotently (re)create `link` → `target` (a dir). Self-clobber guard: if the
    link path IS the target (same path, symlinks not followed), do nothing and return
    None — never unlink the source onto itself. `relative` makes the pair portable
    when moved together (the doc-mirror vision-hyperedge pattern)."""
    target_abs = Path(os.path.abspath(target))
    if Path(os.path.abspath(link)) == target_abs:
        return None
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        link.unlink()
    dst = os.path.relpath(target_abs, os.path.abspath(link.parent)) if relative else target_abs
    link.symlink_to(dst, target_is_directory=True)
    return link


def project(tree_dir: str | Path, target: str | Path, *,
            policy: str = "progressive", link: str = "absolute",
            node: str | None = None, manifest: str | Path | None = None,
            include_root: bool = True, branches: bool = True) -> list[Path]:
    """Project a tree into a skills dir — the ONE deployment op (Move 1).

    policy="progressive"  surface the root (+ first-layer branches) as symlinks;
                          deeper levels stay behind Read-breadcrumbs.
    policy="flat"         project the selected node's tome-table rows (each held
                          framework's skill dir) + the holder node itself, flat —
                          every framework auto-discovers as a top-level skill
                          (née nomicon-atomize). `node` selects the volume node by
                          name or coord (default: the root).
    link="absolute"|"relative"  symlink form (relative = portable-if-moved-together).

    The tree stays the source of truth; the target holds only symlinks. Re-running
    overwrites cleanly (idempotent). Self-clobber-guarded skips return no link.
    """
    tree_dir = Path(tree_dir)
    tree = SkillTree.load(manifest or tree_dir / "skilltree.json")
    target = Path(target)
    rel = link == "relative"
    links: list[Path] = []

    if policy == "progressive":
        if include_root:
            rn = skill_name(tree.root)
            p = _symlink(target / rn, _skill_dir(tree_dir, rn), relative=rel)
            if p:
                links.append(p)
        if branches:
            for child in tree.root.children:
                cn = skill_name(child)
                p = _symlink(target / cn, _skill_dir(tree_dir / child.name, cn), relative=rel)
                if p:
                    links.append(p)
        return links

    if policy != "flat":
        raise ValueError(f"unknown policy {policy!r} (use 'flat' or 'progressive')")

    hit = find_node(tree.root, node or tree.root.name)
    if hit is None:
        raise ValueError(f"no node named/coord {node!r} in the tree")
    vol, path = hit
    node_dir = tree_dir
    for nm in path[1:]:
        node_dir = node_dir / nm

    holder = _skill_dir(node_dir, skill_name(vol))
    for row in vol.frameworks:              # each held framework, flat
        rp = Path(row["skill_path"])
        if not rp.is_absolute():            # relative rows resolve against the holder dir
            rp = holder / rp
        p = _symlink(target / row["name"], rp.parent, relative=rel)
        if p:
            links.append(p)
    # the holder itself (the volume's search/router skill) — skip when the target
    # sits inside the holder's own dir (a symlink loop; the atomize guard)
    if not os.path.abspath(target).startswith(os.path.abspath(node_dir) + os.sep):
        p = _symlink(target / skill_name(vol), _skill_dir(node_dir, skill_name(vol)),
                     relative=rel)
        if p:
            links.append(p)
    return links


def link_tree(tree_dir: str | Path, *, user_skills_dir: str | Path,
              manifest: str | Path | None = None,
              include_root: bool = True, branches: bool = True) -> list[Path]:
    """Symlink a single tree's entry points into the top-level user skills dir.
    (Thin wrapper over `project(policy="progressive", link="absolute")`.)"""
    return project(tree_dir, user_skills_dir, policy="progressive", link="absolute",
                   manifest=manifest, include_root=include_root, branches=branches)


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
    from .materialize import _yaml_scalar as _ys
    (fdir / "SKILL.md").write_text(f"---\nname: {_ys(name)}\ndescription: {_ys(desc)}\n---\n\n{body}\n", encoding="utf-8")
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
