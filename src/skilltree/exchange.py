"""Exchange — many skill trees in one repo, under a master.

An exchange manifest (JSON or YAML) lists member skill trees and a master name:

    name: my-exchange
    master: cc-master
    trees:
      - name: cognition
        manifest: trees/cognition.skilltree.json
      - name: writing
        manifest: trees/writing.skilltree.json

`build` materializes each member tree under `<repo>/trees/<name>/`, then writes a
MASTER root whose `cat`-breadcrumbs point into each member tree's root. The master
is itself a SkillTree-of-trees — the closure again: a tree whose first layer is
the set of member roots. `validate` checks every member tree AND the master's
cross-tree breadcrumbs.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .materialize import node_skill_md
from .materialize import materialize
from .model import SkillTree
from .validate import Violation, _CRUMB_RE, _has_frontmatter
from .validate import validate as validate_tree


@dataclass
class Member:
    name: str
    manifest: str


@dataclass
class Exchange:
    name: str
    master: str
    trees: list[Member]
    base: Path                      # dir the manifest paths resolve against


def load_exchange(path: str | Path) -> Exchange:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        import yaml
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    return Exchange(
        name=data["name"],
        master=data.get("master", "master"),
        trees=[Member(m["name"], m["manifest"]) for m in data.get("trees", [])],
        base=p.resolve().parent,
    )


def _front(name: str, description: str, body: str) -> str:
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{body.rstrip()}\n"


def build(exchange: Exchange, repo_dir: str | Path) -> Path:
    """Materialize every member tree + the master. Returns the master SKILL.md path."""
    repo = Path(repo_dir)
    members: list[tuple[str, Path]] = []   # (member name, member root SKILL.md)
    for m in exchange.trees:
        tree = SkillTree.load((exchange.base / m.manifest).resolve())
        tree_dir = repo / "trees" / m.name
        materialize(tree, tree_dir)
        members.append((m.name, node_skill_md(tree_dir, tree.root.name).resolve()))

    master_md = node_skill_md(repo, exchange.master)
    master_md.parent.mkdir(parents=True, exist_ok=True)
    crumbs = [f"- {name} (tree): Read `{root_md}`" for name, root_md in members]
    body = (f"Master of the **{exchange.name}** exchange — {len(members)} skill tree(s).\n\n"
            "## Trees — pick one and **Read** (the Read tool) into its root\n"
            "Only this master is loaded. Read a tree's root below to load it (a Bash `cat` won't); "
            "each tree then walks its own breadcrumbs:\n\n"
            + "\n".join(crumbs))
    master_md.write_text(_front(exchange.master, f"master of the {exchange.name} exchange", body),
                         encoding="utf-8")

    (repo / "exchange.lock.json").write_text(json.dumps(
        {"name": exchange.name, "master": exchange.master,
         "trees": [{"name": n, "root": str(r)} for n, r in members]}, indent=2), encoding="utf-8")
    return master_md


def validate(repo_dir: str | Path, exchange: Exchange) -> list[Violation]:
    repo = Path(repo_dir)
    out: list[Violation] = []
    # 1. each member tree validates on its own
    for m in exchange.trees:
        for v in validate_tree(repo / "trees" / m.name):
            out.append(Violation(v.severity, f"{m.name}/{v.where}", v.message))
    # 2. the master root + its cross-tree breadcrumbs
    master_md = node_skill_md(repo, exchange.master)
    if not master_md.is_file():
        out.append(Violation("error", exchange.master, f"missing master SKILL.md at {master_md}"))
        return out
    if not _has_frontmatter(master_md):
        out.append(Violation("error", exchange.master, "master SKILL.md lacks frontmatter"))
    found = {Path(p).resolve() for p in _CRUMB_RE.findall(master_md.read_text(encoding="utf-8"))}
    expected = {
        node_skill_md(repo / "trees" / m.name, SkillTree.load((exchange.base / m.manifest).resolve()).root.name).resolve()
        for m in exchange.trees
    }
    for missing in expected - found:
        out.append(Violation("error", exchange.master, f"no master breadcrumb for tree root → {missing}"))
    for p in found:
        if not Path(p).is_file():
            out.append(Violation("error", exchange.master, f"dead master breadcrumb: `cat {p}`"))
    return out


def is_valid(repo_dir: str | Path, exchange: Exchange) -> bool:
    return not any(v.severity == "error" for v in validate(repo_dir, exchange))
