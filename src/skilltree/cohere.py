"""cohere.py — the FRONT half of skilltree: discover → cohere → emit (in place).

`materialize` only goes one way (tree → disk, destructively). This module is the
missing inverse + the drift gate the rest of the system needs to *use itself*:

  discover(root)  →  read the LIVE filesystem and reconstruct the tree that is
                     actually there (reality), independent of any manifest.
  cohere(root)    →  diff reality against the ENGINEERED shape (skilltree.json,
                     the canonical tree). Decoherence = the breadcrumbs/coords on
                     disk no longer match the tree's real shape. This is what a
                     cron runs: "you decohered X — look at the tree shape."
  emit(root)      →  rewrite each node's coord + `cat`-breadcrumbs + index summary
                     IN PLACE (no rmtree), so reality matches the engineered shape
                     again — and, for a bare forest, ROOT it (the forest→tree fix).

The law (rule 01): a bare forest is the bug. `cohere` finds it; `emit` roots it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .model import SkillTree, TreeNode, assign_coords, compose_summary, skill_name

# dirs that are never tree nodes
_SKIP = {".claude", "kb", "__pycache__", ".git", "node_modules", ".aios.src"}
# a coord-prefixed skill identity: "0.1.2-some-name" → ("0.1.2", "some-name")
_COORD_RE = re.compile(r"^(\d+(?:\.\d+)*)-(.+)$")
# everything from the first generated section to EOF (materialize appends them last)
_SECT_RE = re.compile(r"\n+## Index summary\b.*\Z", re.S)
_CRUMB_RE = re.compile(r"`([^`]+?)/SKILL\.md`")     # the path-before-SKILL.md, verb-agnostic
_CRUMB = "- {name} ({kind}): Read `{path}`"          # the verb is the Read TOOL, never `cat`


def _parse_ident(sdir_name: str) -> tuple[str | None, str]:
    m = _COORD_RE.match(sdir_name)
    return (m.group(1), m.group(2)) if m else (None, sdir_name)


def _front(skill_md: Path) -> dict:
    """Parse the YAML-ish frontmatter of a SKILL.md (name/description lines)."""
    text = skill_md.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    if text.lstrip().startswith("---"):
        for line in text.split("---", 2)[1].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip()
    return out


def _skills_dir(node_dir: Path) -> Path:
    """Where a node keeps its skills. A `.claude` dir (the USER level, `~/.claude`)
    holds them at `<.claude>/skills`; a project/branch dir at `<dir>/.claude/skills`."""
    return node_dir / "skills" if node_dir.name == ".claude" else node_dir / ".claude" / "skills"


def _skill_dirs_in(node_dir: Path) -> list[Path]:
    cs = _skills_dir(node_dir)
    if not cs.exists():
        return []
    return sorted(d for d in cs.iterdir() if d.is_dir() and (d / "SKILL.md").exists())


def _child_dirs(node_dir: Path) -> list[Path]:
    """Plain sub-dirs that are themselves tree nodes (carry their own .claude/skills)."""
    return sorted(d for d in node_dir.iterdir()
                  if d.is_dir() and d.name not in _SKIP and (d / ".claude" / "skills").exists())


# ── discover: live filesystem → SkillTree (reality) ──────────────────────────
def _discover_node(node_dir: Path) -> tuple[list[TreeNode], list[str]]:
    """Reconstruct the node(s) rooted at `node_dir`. Returns (nodes, strays):
    `strays` = names of extra skills sharing a node's .claude/skills (a decoherence
    smell — a proper node owns exactly one skill in its own root)."""
    sdirs = _skill_dirs_in(node_dir)
    strays: list[str] = []

    # children come from the plain sub-dirs that are nodes
    children: list[TreeNode] = []
    for cd in _child_dirs(node_dir):
        kids, kstray = _discover_node(cd)
        children.extend(kids)
        strays.extend(kstray)

    if not sdirs:
        return children, strays           # a plain container dir (e.g. the discover root)

    # an UNCOORDINATED skill ranks LAST (it can't be the root of a coordinated subtree).
    def _key(d: Path):
        c, _ = _parse_ident(d.name)
        return (c.count(".") if c else 999, c or "~", d.name)

    def _leaf(sd: Path) -> TreeNode:
        coord, name = _parse_ident(sd.name)
        desc = re.sub(r"^\[[\d.]+\]\s*", "", _front(sd / "SKILL.md").get("description", ""))
        # skill_src = the CURRENT on-disk location (so emit can relocate it when tree-ifying)
        return TreeNode(name=name, kind="skill", description=desc or None,
                        coord=coord, skill_src=str(sd))

    # A node OWNS its subtree only when there's real NESTING (child node-dirs) or it is
    # a lone skill. A pile of many skills with no nesting is a FLAT FOREST — even if a few
    # carry leftover coord prefixes (those are just oddly-named flat skills, not a root).
    if children or len(sdirs) == 1:
        own = sorted(sdirs, key=_key)[0]
        strays.extend(d.name for d in sdirs if d is not own)
        node = _leaf(own)
        node.children = children
        return [node], strays
    return [_leaf(d) for d in sdirs] + children, strays


def discover(root: str | Path, *, forest_name: str | None = None) -> SkillTree:
    """Read the live filesystem from `root` down and reconstruct the tree as it
    ACTUALLY is. A bare forest (many roots, no single parent) is wrapped in a
    SYNTHESIZED root so the result is always a tree (the thing it should become)."""
    root = Path(root)
    nodes, _ = _discover_node(root)
    if len(nodes) == 1:
        return SkillTree(nodes[0])
    return SkillTree(TreeNode(
        name=forest_name or root.name, kind="sc",
        description=f"(synthesized root over a bare forest of {len(nodes)})",
        children=nodes))


# ── cohere: reality vs the engineered shape → drift findings ─────────────────
@dataclass
class Finding:
    kind: str           # bare_forest | uncoordinated | coord_drift | stale_breadcrumb | stray_skill | missing_node | extra_node
    coord: str | None
    name: str
    detail: str

    def __str__(self) -> str:
        at = f"[{self.coord}] " if self.coord else ""
        return f"{self.kind}: {at}{self.name} — {self.detail}"


def _node_dir(root: Path, path: list[str]) -> Path:
    """Tree-path dir for a node reached by plain names from the root (root = root dir)."""
    d = root
    for nm in path[1:]:
        d = d / nm
    return d


def cohere(root: str | Path) -> list[Finding]:
    """Decoherence report: how the on-disk tree has drifted from its engineered
    shape. With a `skilltree.json` it diffs reality against that canon; without one
    the dir is a bare forest by definition (the rule-01 violation)."""
    root = Path(root)
    findings: list[Finding] = []
    manifest = root / "skilltree.json"

    if not manifest.exists():
        live = discover(root)
        kids = live.root.children
        if live.root.description and "synthesized root" in live.root.description:
            findings.append(Finding("bare_forest", None, live.root.name,
                f"no skilltree.json; {len(kids)} top skills with no root — run `emit --root` to tree-ify"))
        if any(c.coord is None for c in live.nodes()):
            findings.append(Finding("uncoordinated", None, live.root.name,
                "nodes have no coordinates (never materialized with coords)"))
        return findings

    canon = SkillTree.load(manifest)
    assign_coords(canon.root)                      # what the coords SHOULD be

    # walk canon with tree-path; check disk reality at each node
    def walk(node: TreeNode, path: list[str]) -> None:
        ndir = _node_dir(root, path)
        sname = skill_name(node)
        smd = ndir / ".claude" / "skills" / sname / "SKILL.md"
        # 1. node present on disk at its canonical coord?
        if not smd.exists():
            # maybe present under a DIFFERENT coord (coord drift) or missing entirely
            alt = sorted((ndir / ".claude" / "skills").glob("*")) if (ndir / ".claude" / "skills").exists() else []
            alt_named = [a.name for a in alt if _parse_ident(a.name)[1] == node.name]
            if alt_named:
                findings.append(Finding("coord_drift", node.coord, node.name,
                    f"on disk as {alt_named[0]!r}, canon says {sname!r}"))
            else:
                findings.append(Finding("missing_node", node.coord, node.name,
                    f"declared in manifest, absent on disk ({smd})"))
        else:
            # 2. branch breadcrumbs match the real children?
            if node.children:
                body = smd.read_text(encoding="utf-8")
                # compare by PLAIN name (strip the coord prefix); coord drift is its own finding
                have = {_parse_ident(Path(p).name)[1] for p in _CRUMB_RE.findall(body)}
                want = {c.name for c in node.children}
                missing = want - have
                extra = have - want
                if missing or extra:
                    findings.append(Finding("stale_breadcrumb", node.coord, node.name,
                        f"breadcrumbs {'missing ' + ','.join(sorted(missing)) if missing else ''}"
                        f"{' / ' if missing and extra else ''}"
                        f"{'dangling ' + ','.join(sorted(extra)) if extra else ''}".strip()))
            # 3. extra strays sharing this node's root
            _, strays = _discover_node(ndir)
            for s in strays:
                findings.append(Finding("stray_skill", node.coord, node.name,
                    f"extra skill {s!r} sits in this node's root (not in the tree)"))
        for c in node.children:
            walk(c, path + [c.name])

    walk(canon.root, [canon.root.name])
    return findings


# ── emit: rewrite coords + breadcrumbs + index IN PLACE (non-destructive) ─────
def _rewrite_node_md(smd: Path, node: TreeNode, node_dir: Path) -> None:
    """Refresh ONLY the coord prefix + Index/Descend sections of an existing
    SKILL.md, preserving the hand-written body above them. Creates the file (a
    stub) if absent (e.g. a freshly synthesized forest root)."""
    sname = skill_name(node)

    def _base_from(text: str) -> str:
        body = text.split("---", 2)[-1] if text.lstrip().startswith("---") else text
        return _SECT_RE.sub("", body).strip()

    src_md = Path(node.skill_src) / "SKILL.md" if node.skill_src else None
    if smd.exists():                                   # in-place re-cohere: keep existing body
        base = _base_from(smd.read_text(encoding="utf-8"))
    elif src_md and src_md.exists():                   # relocation: carry the body from skill_src
        smd.parent.mkdir(parents=True, exist_ok=True)
        base = _base_from(src_md.read_text(encoding="utf-8"))
    else:                                              # fresh stub (e.g. a synthesized root)
        smd.parent.mkdir(parents=True, exist_ok=True)
        base = f"SkillTree {node.kind} node `{node.name}`."

    desc = node.description or compose_summary(node, full=False)
    desc = re.sub(r"^\[[\d.]+\]\s*", "", desc)
    if node.coord:
        desc = f"[{node.coord}] {desc}"

    if node.children:
        crumbs = [_CRUMB.format(
            name=skill_name(c), kind=c.kind,
            path=(node_dir / c.name / ".claude" / "skills" / skill_name(c) / "SKILL.md").resolve())
            for c in node.children]
        tail = (f"\n\n## Index summary\n{compose_summary(node, full=True)}\n\n"
                f"## Descend — the next layer ({len(node.children)})\n"
                "Only this layer is loaded now. To descend, use the **Read tool** on a child "
                "below — that injects the child's layer. A Bash `cat` reads the bytes but loads "
                "nothing; you must use the Read tool:\n\n" + "\n".join(crumbs))
    else:
        tail = ""
    out = f"---\nname: {sname}\ndescription: {desc}\n---\n\n{base}{tail}\n"
    smd.write_text(out, encoding="utf-8")


JOURNAL = ".emit-journal.json"   # the reversibility receipt written by a tree-ifying emit


def emit(root: str | Path, *, root_forest: bool = False,
         forest_name: str | None = None) -> dict:
    """Re-cohere the tree IN PLACE: assign coords + rewrite every node's
    breadcrumbs/index from the canonical shape, without destroying content.

    No skilltree.json + `root_forest=True` → discover the bare forest, synthesize
    a root, and **tree-ify it**: each flat leaf is MOVED WHOLESALE into its nested
    node-dir (all its files preserved — *not* a body-only re-render), so it stops
    auto-loading. Every move is JOURNALED to `.emit-journal.json` so `unemit` can
    reverse it exactly (your cache-for-reversibility requirement)."""
    root = Path(root)
    manifest = root / "skilltree.json"
    synthesized = False
    if manifest.exists():
        tree = SkillTree.load(manifest)
    else:
        if not root_forest:
            return {"ok": False, "error": "no skilltree.json; pass root_forest=True to tree-ify a bare forest"}
        tree = discover(root, forest_name=forest_name)
        synthesized = True

    assign_coords(tree.root)
    journal: list[dict] = []      # only populated when synthesizing (i.e. when we MOVE)
    n = 0

    def walk(node: TreeNode, node_dir: Path) -> None:
        nonlocal n
        target_dir = node_dir / ".claude" / "skills" / skill_name(node)
        old_src = Path(node.skill_src) if node.skill_src else None
        if synthesized and old_src and old_src.exists() \
                and old_src.resolve() != target_dir.resolve():
            # LOSSLESS relocation into the nested node-dir, journaled for unemit.
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            if old_src.is_symlink():
                # a symlink'd skill (the common ~/.claude case): de-symlink — copy the
                # RESOLVED content into the node-dir (so coord/breadcrumbs are writable),
                # drop the link, journal it so unemit recreates the EXACT symlink.
                journal.append({"op": "desymlink", "symlink": str(old_src),
                                "link": os.readlink(old_src), "to": str(target_dir)})
                shutil.copytree(old_src.resolve(), target_dir, symlinks=False)
                old_src.unlink()
            else:
                # a real dir: move the WHOLE dir (baggage and all), journal the bytes.
                orig = (old_src / "SKILL.md").read_text(encoding="utf-8") \
                    if (old_src / "SKILL.md").exists() else ""
                journal.append({"op": "move", "from": str(old_src), "to": str(target_dir),
                                "skill_md": orig})
                shutil.move(str(old_src), str(target_dir))
            _rewrite_node_md(target_dir / "SKILL.md", node, node_dir)
        else:
            existed = (target_dir / "SKILL.md").exists()
            _rewrite_node_md(target_dir / "SKILL.md", node, node_dir)
            if synthesized and not existed:        # a freshly-created node (the synth root)
                journal.append({"op": "create", "path": str(target_dir)})
        n += 1
        for c in node.children:
            walk(c, node_dir / c.name)

    walk(tree.root, root)
    tree.save(manifest)
    if synthesized:
        journal.append({"op": "manifest", "path": str(manifest)})
        (root / JOURNAL).write_text(json.dumps(journal, indent=2), encoding="utf-8")
    return {"ok": True, "nodes": n, "synthesized_root": synthesized,
            "root": skill_name(tree.root),
            "moves": sum(1 for e in journal if e["op"] in ("move", "desymlink")),
            "journal": str(root / JOURNAL) if synthesized else None}


def _prune_empty(d: Path, stop: Path) -> None:
    """Remove `d` and its now-empty parents, up to (not including) `stop`."""
    d = Path(d)
    stop = Path(stop).resolve()
    while d.resolve() != stop and d.is_dir() and not any(d.iterdir()):
        d.rmdir()
        d = d.parent


def unemit(root: str | Path) -> dict:
    """Reverse the last tree-ifying `emit` by replaying `.emit-journal.json`
    backwards: move every relocated dir back to where it came from, restore its
    original SKILL.md, delete the synthesized root + manifest, prune the empty
    nesting. A clean, lossless undo — nothing was destroyed, only moved-with-a-receipt."""
    root = Path(root)
    jpath = root / JOURNAL
    if not jpath.exists():
        return {"ok": False, "error": f"no {JOURNAL} — nothing to reverse"}
    journal = json.loads(jpath.read_text(encoding="utf-8"))
    moved = removed = 0
    for entry in reversed(journal):
        op = entry["op"]
        if op == "move":
            frm, to = Path(entry["from"]), Path(entry["to"])
            if to.exists():
                frm.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(to), str(frm))
                if entry.get("skill_md"):
                    (frm / "SKILL.md").write_text(entry["skill_md"], encoding="utf-8")
                _prune_empty(to.parent, root)
                moved += 1
        elif op == "desymlink":
            sympath, to = Path(entry["symlink"]), Path(entry["to"])
            if to.exists():                         # drop the de-symlinked copy
                shutil.rmtree(to)
                _prune_empty(to.parent, root)
            if not (sympath.exists() or sympath.is_symlink()):   # recreate the exact link
                sympath.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(entry["link"], sympath)
            moved += 1
        elif op == "create":
            p = Path(entry["path"])
            if p.exists():
                shutil.rmtree(p)
                _prune_empty(p.parent, root)
                removed += 1
        elif op == "manifest":
            p = Path(entry["path"])
            if p.exists():
                p.unlink()
    jpath.unlink()
    return {"ok": True, "moved_back": moved, "removed": removed}


# ── notifications: cohere → a self-managed TOP-LEVEL rule (the decoherence cron) ─
# The lord at the top (`~/.claude`) can't watch the tree by hand, so a background
# check writes its verdict into ONE user-level rule that leaks into every session's
# system prompt: "you decohered X — here's the tree shape, run the skill to fix it."
# The cron is READ-ONLY on the tree (it never emits/relocates — that stays
# agent-initiated, because emit can move real skills); it only rewrites this rule.
_SEVERITY = {
    "bare_forest": "ERROR", "missing_node": "ERROR", "coord_drift": "ERROR",
    "stale_breadcrumb": "WARN", "stray_skill": "WARN", "uncoordinated": "WARN",
    "extra_node": "WARN",
}
_BADGE = {"ERROR": "🔴", "WARN": "🟡"}
NOTIFY_RULE = "00-system-notifications.md"      # sorts first → seen first in the rule block

_NOTIFY_HEAD = (
    "# [SKILLTREE] System Notifications\n\n"
    "> This rule posts system notifications. It is **automatically managed by SkillTree**.\n"
    "> **Do not edit this rule** — it is rewritten by the decoherence check whenever the\n"
    "> SkillTree's on-disk shape drifts from its engineered (coherent) form.\n"
)


def render_notifications(findings: list[Finding], *, root: str | Path) -> str:
    """Render the body of the self-managed `00-system-notifications` rule."""
    lines = [_NOTIFY_HEAD, "## Warnings", ""]
    if not findings:
        lines.append("None. Systems nominal.")
        return "\n".join(lines) + "\n"
    errs = [f for f in findings if _SEVERITY.get(f.kind) == "ERROR"]
    warns = [f for f in findings if _SEVERITY.get(f.kind) != "ERROR"]
    for f in errs + warns:
        sev = _SEVERITY.get(f.kind, "WARN")
        lines.append(f"- {_BADGE[sev]} **{sev}** — {f}")
    lines += [
        "", f"## To fix these ({len(errs)} error(s), {len(warns)} warning(s))",
        "",
        f"The SkillTree under `{root}` has **decohered**: its `cat`-breadcrumbs / coordinates "
        "no longer match the tree's real shape (rule 01 — a bare forest or stale wiring).",
        "",
        "**Run the `skilltree` skill** (the recohere flow). In short: `skilltree emit <root>` "
        "re-coheres the tree in place (add `--root` to tree-ify a bare forest). This notice "
        "clears itself on the next check.",
    ]
    return "\n".join(lines) + "\n"


def write_notifications(root: str | Path, *, rules_dir: str | Path,
                        only_if_changed: bool = True) -> dict:
    """Run `cohere(root)`, render the verdict, and write the `system_notifications`
    rule into `rules_dir` (e.g. `~/.claude/rules`). Idempotent: only rewrites when
    the content changed (so a nominal tree doesn't churn the file every check)."""
    findings = cohere(root)
    content = render_notifications(findings, root=Path(root))
    rules_dir = Path(rules_dir)
    rules_dir.mkdir(parents=True, exist_ok=True)
    target = rules_dir / NOTIFY_RULE
    changed = (not target.exists()) or target.read_text(encoding="utf-8") != content
    if changed or not only_if_changed:
        target.write_text(content, encoding="utf-8")
    errs = sum(1 for f in findings if _SEVERITY.get(f.kind) == "ERROR")
    return {"findings": len(findings), "errors": errs, "warnings": len(findings) - errs,
            "nominal": not findings, "changed": changed, "path": str(target)}


def watch(root: str | Path, *, rules_dir: str | Path, interval: float = 300,
          iterations: int | None = None, sleep=None) -> dict:
    """The decoherence loop: every `interval` seconds, re-check the tree and refresh
    the notification rule. `iterations` bounds it (None = forever, for the real cron;
    1 = a single check, for tests). READ-ONLY on the tree — only the rule is written."""
    import time
    _sleep = sleep or time.sleep
    n = 0
    last: dict = {}
    while iterations is None or n < iterations:
        last = write_notifications(root, rules_dir=rules_dir)
        n += 1
        if iterations is not None and n >= iterations:
            break
        _sleep(interval)
    return {"checks": n, "last": last}
