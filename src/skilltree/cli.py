"""skilltree — build a `cat`-breadcrumb tree of skill dirs from JSON, and validate it."""
from __future__ import annotations

from pathlib import Path
import tempfile

import click

from .materialize import materialize, node_skill_md
from .model import SkillTree, TreeNode
from .validate import validate


@click.group()
@click.version_option(message="skilltree %(version)s")
def main() -> None:
    """SkillTree — a nested tree of skill dirs wired by `cat`-breadcrumbs (validated)."""


@main.command(name="discover")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
def discover_cmd(root: Path) -> None:
    """Read the live filesystem and print the tree that is ACTUALLY there
    (every dir with a .claude/skills, nested by plain-dir path)."""
    from .cohere import discover
    from .model import skill_name

    tree = discover(root)

    def show(node, depth=0):
        click.echo("  " * depth + f"{skill_name(node)} ({node.kind})")
        for c in node.children:
            show(c, depth + 1)
    show(tree.root)


@main.command(name="cohere")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
def cohere_cmd(root: Path) -> None:
    """Report DECOHERENCE: how the on-disk tree drifted from its engineered shape
    (bare forest, stale breadcrumbs, coord drift, strays). Exit 1 if any drift —
    so a cron can notify on a non-zero exit."""
    from .cohere import cohere
    findings = cohere(root)
    if not findings:
        click.echo("✓ coherent — the tree shape and the breadcrumbs agree")
        return
    click.echo(f"⚠ {len(findings)} decoherence finding(s):")
    for f in findings:
        click.echo(f"  - {f}")
    raise SystemExit(1)


@main.command(name="emit")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--root-forest", is_flag=True, help="tree-ify a bare forest (synthesize + save a root)")
@click.option("--name", "forest_name", default=None, help="name for the synthesized root")
def emit_cmd(root: Path, root_forest: bool, forest_name: str | None) -> None:
    """Re-cohere IN PLACE: reassign coords + rewrite breadcrumbs/index from the
    canonical shape (non-destructive). With --root-forest, root a bare forest."""
    from .cohere import emit
    report = emit(root, root_forest=root_forest, forest_name=forest_name)
    if not report.get("ok"):
        click.echo(f"✗ {report.get('error')}")
        raise SystemExit(1)
    extra = " (synthesized root)" if report.get("synthesized_root") else ""
    moves = f", {report.get('moves')} moved" if report.get("moves") else ""
    click.echo(f"✓ emitted {report['nodes']} node(s) under {report['root']}{extra}{moves}")
    if report.get("journal"):
        click.echo(f"  journal: {report['journal']}  (reverse with `skilltree unemit`)")


@main.command(name="unemit")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
def unemit_cmd(root: Path) -> None:
    """Reverse the last tree-ifying `emit`: replay `.emit-journal.json` backwards —
    move every relocated skill dir back, restore its SKILL.md, drop the synthesized
    root + manifest. Lossless undo."""
    from .cohere import unemit
    rep = unemit(root)
    if not rep.get("ok"):
        click.echo(f"✗ {rep.get('error')}")
        raise SystemExit(1)
    click.echo(f"✓ reversed: {rep['moved_back']} dir(s) moved back, {rep['removed']} synthesized node(s) removed")


_DEFAULT_RULES = Path.home() / ".claude" / "rules"


@main.command(name="notify")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--rules-dir", type=click.Path(path_type=Path), default=None,
              help="where to write the managed rule (default ~/.claude/rules)")
def notify_cmd(root: Path, rules_dir: Path | None) -> None:
    """One decoherence check → (re)write the self-managed `system_notifications`
    rule. READ-ONLY on the tree; only the rule file changes. Exit 1 on any drift."""
    from .cohere import write_notifications
    rep = write_notifications(root, rules_dir=rules_dir or _DEFAULT_RULES)
    state = "nominal" if rep["nominal"] else f"{rep['errors']} error(s), {rep['warnings']} warning(s)"
    wrote = "rewrote" if rep["changed"] else "unchanged"
    click.echo(f"[SKILLTREE] {state} — {wrote} {rep['path']}")
    raise SystemExit(0 if rep["nominal"] else 1)


@main.command(name="watch")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--rules-dir", type=click.Path(path_type=Path), default=None,
              help="where to write the managed rule (default ~/.claude/rules)")
@click.option("--interval", default=300, type=float, help="seconds between checks (default 300)")
@click.option("--once", is_flag=True, help="run a single check and exit (for testing)")
def watch_cmd(root: Path, rules_dir: Path | None, interval: float, once: bool) -> None:
    """The decoherence cron: every --interval seconds, re-check the tree and refresh
    the `system_notifications` rule. Start as a background process. READ-ONLY on the
    tree (it only writes the rule); the FIX is agent-initiated via the skilltree skill."""
    from .cohere import watch
    rd = rules_dir or _DEFAULT_RULES
    click.echo(f"[SKILLTREE] watching {root} every {interval:.0f}s → {rd}")
    watch(root, rules_dir=rd, interval=interval, iterations=1 if once else None)


@main.command(name="search")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("query")
@click.option("--scope", "scope_coord", default=None, help="restrict to a coordinate subtree, e.g. 0.1")
@click.option("--facet", default=None, help="GlyphSteer glyph to facet on, e.g. 🏆 (needs --legend)")
@click.option("--legend", type=click.Path(exists=True, path_type=Path), default=None,
              help="path to a GlyphSteer legend.json (glyph↔meaning↔tag)")
@click.option("--limit", default=10, type=int)
def search_cmd(root, query, scope_coord, facet, legend, limit):
    """BM25 search over a materialized tree, optionally scoped to a coordinate subtree
    and/or faceted by a GlyphSteer glyph (with --legend)."""
    from .search import search_tree
    vocab = None
    if legend:
        from glyphsteer import load_legend, render_legend
        vocab = load_legend(legend)
        click.echo(render_legend(vocab))
    hits = search_tree(root, query, scope_coord=scope_coord, facet=facet, vocab=vocab, limit=limit)
    if not hits:
        click.echo("(no matches)")
        return
    for h in hits:
        coord = f"[{h['coord']}] " if h["coord"] else ""
        badge = f"{h.get('glyphs')} " if h.get("glyphs") else ""
        click.echo(f"  {badge}{coord}{h['name']} — {h['description']}")


@main.command(name="report-missed")
@click.option("--needed", required=True, help="the skill/capability that was needed")
@click.option("--happened", required=True, help="what you did instead / what went wrong")
@click.option("--suggests", default=None, help="proposed skill name + one-line purpose")
@click.option("--by", default="agent")
@click.option("--reports", "reports_path", default=None, help="reports store (default ~/.claude/skill-reports.json)")
def report_missed_cmd(needed, happened, suggests, by, reports_path):
    """File a missed-skill report (a needed skill didn't exist)."""
    from .reports import DEFAULT_REPORTS, report_missed
    e = report_missed(reports_path or DEFAULT_REPORTS, needed=needed, happened=happened, suggests=suggests, by=by)
    click.echo(f"✓ filed {e['id']} (missed_skill) — needed: {needed!r}")


@main.command(name="mark-problem")
@click.option("--skill", required=True, help="the skill that should have fired")
@click.option("--expected", required=True, help="what you expected it to do")
@click.option("--happened", required=True, help="what happened instead")
@click.option("--by", default="user")
@click.option("--reports", "reports_path", default=None)
def mark_problem_cmd(skill, expected, happened, by, reports_path):
    """Mark 'expected this skill to be used, but it wasn't'."""
    from .reports import DEFAULT_REPORTS, mark_problem
    e = mark_problem(reports_path or DEFAULT_REPORTS, skill=skill, expected=expected, happened=happened, by=by)
    click.echo(f"✓ filed {e['id']} (expected_not_used) — skill: {skill!r}")


@main.command(name="reports")
@click.option("--reports", "reports_path", default=None)
@click.option("--kind", default=None)
def reports_cmd(reports_path, kind):
    """Show the open skill reports (the improver's queue)."""
    from .reports import DEFAULT_REPORTS, list_reports, summary
    rp = reports_path or DEFAULT_REPORTS
    s = summary(rp)
    click.echo(f"reports: {s['open']} open / {s['total']} total  {s['open_by_kind']}")
    for r in list_reports(rp, kind=kind):
        head = r.get("needed") or r.get("skill") or "?"
        click.echo(f"  {r['id']} [{r['kind']}] by {r['by']}: {head}")


@main.command(name="build")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("root", type=click.Path(path_type=Path))
def build_cmd(manifest: Path, root: Path) -> None:
    """Materialize a SkillTree from a JSON MANIFEST into ROOT, then validate."""
    tree = SkillTree.load(manifest)
    materialize(tree, root)
    issues = validate(root)
    errors = [v for v in issues if v.severity == "error"]
    click.echo(f"built {len(tree.nodes())} nodes at {root}")
    for v in issues:
        click.echo(f"  {'✗' if v.severity == 'error' else '⚠'} [{v.where}] {v.message}")
    if errors:
        raise SystemExit(f"✗ INVALID — {len(errors)} error(s)")
    click.echo(f"✓ valid — root: cat {node_skill_md(root, tree.root.name)}")


@main.command(name="validate")
@click.argument("root", type=click.Path(exists=True, file_okay=False, path_type=Path))
def validate_cmd(root: Path) -> None:
    """Validate a materialized SkillTree at ROOT."""
    issues = validate(root)
    for v in issues:
        click.echo(f"  {'✗' if v.severity == 'error' else '⚠'} [{v.where}] {v.message}")
    if any(v.severity == "error" for v in issues):
        raise SystemExit("✗ INVALID")
    click.echo("✓ valid — every breadcrumb resolves.")


@main.group()
def exchange() -> None:
    """Many skill trees in one repo, under a master."""


@exchange.command(name="build")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("repo", type=click.Path(path_type=Path))
def exchange_build(manifest: Path, repo: Path) -> None:
    """Materialize every member tree + the master from an exchange MANIFEST."""
    from .exchange import build, load_exchange, validate
    ex = load_exchange(manifest)
    master = build(ex, repo)
    issues = validate(repo, ex)
    click.echo(f"built exchange '{ex.name}' — {len(ex.trees)} tree(s) + master at {master}")
    for v in issues:
        click.echo(f"  {'✗' if v.severity == 'error' else '⚠'} [{v.where}] {v.message}")
    if any(v.severity == "error" for v in issues):
        raise SystemExit("✗ INVALID")
    click.echo("✓ valid — master + every member tree resolve.")


@exchange.command(name="validate")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("repo", type=click.Path(exists=True, file_okay=False, path_type=Path))
def exchange_validate(manifest: Path, repo: Path) -> None:
    """Validate a built exchange REPO against its MANIFEST."""
    from .exchange import load_exchange, validate
    for v in validate(repo, load_exchange(manifest)):
        click.echo(f"  {'✗' if v.severity == 'error' else '⚠'} [{v.where}] {v.message}")


@main.command()
def demo() -> None:
    """Build a breadcrumb tree, walk it by `cat`, validate, then break a breadcrumb."""
    tree = SkillTree(TreeNode("cc-skill-tree", "sc", description="root of the cognition skill tree", children=[
        TreeNode("debug", "cor", description="how to debug", children=[
            TreeNode("symptom-attn", "ac", description="attend to the symptom"),
        ]),
        TreeNode("explain", "cor", description="how to explain", children=[
            TreeNode("simplify-attn", "ac", description="attend to the simplest form"),
        ]),
    ]))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "cc_tree_test"
        materialize(tree, root)

        click.echo("══ 1. only the ROOT auto-loads; everything else is reached by `cat` ══")
        rootmd = node_skill_md(root, "cc-skill-tree")
        click.echo(f"  auto-loaded: {rootmd}")
        click.echo("  ── its body (the breadcrumbs) ──")
        click.echo("\n".join("    " + l for l in rootmd.read_text().splitlines() if l.strip()))

        click.echo("\n══ 2. follow a breadcrumb down to a leaf ══")
        debugmd = node_skill_md(root / "debug", "debug")
        leafmd = node_skill_md(root / "debug" / "symptom-attn", "symptom-attn")
        click.echo(f"  cat {debugmd}  → then → cat {leafmd}")

        click.echo("\n══ 3. validate (the harness) ══")
        click.echo(f"  {'✓ valid' if not validate(root) else 'issues:'}")
        for v in validate(root):
            click.echo(f"    {v.severity}: [{v.where}] {v.message}")

        click.echo("\n══ 4. corrupt a breadcrumb (rename a child dir); substrate stays silent ══")
        (root / "debug" / "symptom-attn").rename(root / "debug" / "renamed-away")
        for v in validate(root):
            click.echo(f"    ✗ [{v.where}] {v.message}")


if __name__ == "__main__":
    main()
