# skilltree

Turn a **flat** folder of skills (or any `.claude` directory) into a **navigable tree** that a model can walk one layer at a time — and keep it coherent.

Claude Code auto-loads `~/.claude/skills` (and a project's `.claude/skills`) **one layer deep**: every skill directory loads at once, and a `.claude` nested inside another `.claude` never loads. At a handful of skills that is fine; at a hundred it is *melt* — the whole pile lands in context every turn, and tool selection degrades as the set grows. The substrate ships the nodes and forbids the edge.

`skilltree` imposes the missing structure on that flat substrate, using the only three levers the platform leaves open:

1. **placement** — each node is a plain directory carrying its own one-skill `.claude/`; the path *is* the coordinate (`0` → `0.1` → `0.1.1`);
2. **the inert-nested-`.claude` boundary** — only the top layer auto-loads, so deeper nodes stay out of context until entered;
3. **breadcrumbs** — each node's `SKILL.md` ends with an index summary of its subtree and explicit instructions to **Read** its children.

You load one layer and *walk*; you never load the pile.

## The load mechanism it exploits (verified against the runtime)

The design rests on one fact about Claude Code, which `skilltree` verifies rather than assumes:

> Your context + Skill-tool menu = `~/.claude` (always, one layer) **+ every project directory you _Read into_** (its `CLAUDE.md` + `.claude/rules` + `.claude/skills`, dynamically, one layer). Descendants don't load until Read; out-of-project directories don't trigger it; **the trigger is the Read tool, not `cat`** (a shell `cat` of the same file injects nothing).

So descending the tree is a **Read into the next node** — which loads exactly that node's layer and no more. That is why the breadcrumbs say **Read**, not `cat`: a `cat` reads the bytes but loads nothing.

## Install

```bash
pip install -e .          # from a clone
# or: pip install skilltree
```

This installs the `skilltree` CLI.

## Quickstart

```bash
# 1. See the tree that is actually on disk
skilltree discover ~/my-skills

# 2. Check coherence — is it a tree, or a bare forest with stale wiring?
skilltree cohere ~/my-skills          # exits non-zero on drift

# 3. Tree-ify a flat forest IN PLACE (lossless: whole dirs moved, baggage kept,
#    symlinks de-symlinked; every move journaled to .emit-journal.json)
skilltree emit ~/my-skills --root-forest --name my-skills

# 4. ...and undo it exactly, byte-for-byte, any time
skilltree unemit ~/my-skills

# 5. Search the tree (BM25), scoped to a coordinate subtree
skilltree search ~/my-skills "deploy rollback" --scope 0.1
```

Programmatic use mirrors the CLI:

```python
from skilltree import discover, cohere, emit, materialize, SkillTree, TreeNode

findings = cohere("~/my-skills")              # list[Finding] — the drift report
emit("~/my-skills", root_forest=True)         # tree-ify, journaled
materialize(SkillTree(TreeNode("root", "sc", children=[...])), "out/", coords=True)
```

## Self-management (it keeps itself coherent)

A structure the platform won't maintain decays back to the flat forest it replaced — so `skilltree` maintains itself:

- **`discover`** reconstructs the on-disk tree from reality, independent of any manifest.
- **`cohere`** reports drift between reality and the engineered shape — a bare (unrooted) forest, a stale breadcrumb, a coordinate that no longer matches, a skill dropped in flat.
- **`emit`** re-coheres in place; given a flat forest it tree-ifies it, **moving each skill directory whole** (all of its files preserved — no body-only re-render, no `rmtree`) and **de-symlinking** any symlink'd skill, journaling every move so **`unemit`** restores the prior state byte-for-byte.
- A scheduled check (`skilltree watch <root>`) writes its verdict into a single managed rule, so a decohered tree announces itself in every subsequent session.

## How a tree looks on disk

```
domain/.claude/skills/0-domain/SKILL.md          # root menu — the only node that auto-loads
domain/A/.claude/skills/0.1-A/SKILL.md            # child A   — loaded only when Read
domain/A/A1/.claude/skills/0.1.1-A1/SKILL.md      # grandchild — one level deeper
domain/B/.claude/skills/0.2-B/SKILL.md
```

The root menu carries an index summary (so a query about `A1` still finds the branch that leads to it) and the descend breadcrumbs (the out-edges, expressed as the Read that loads them). A coordinate stands in for identity; a breadcrumb stands in for an edge — emulations of what a graph would hold natively.

## Roadmap

- **v1 — Claude Code** *(shipping)* — the tree, the front half (`discover`/`cohere`/`emit`/`unemit`), the decoherence watch. The descent mechanic is Claude-Code-specific by design.
- **v2 — Cross-format adapters** — per-format, **not** symlinks: the descent mechanic doesn't generalize (Codex resolves once at cwd; Gemini eager-loads the whole tree). `SKILL.md` + `.agents/skills` is the portable foundation.
- **v3 — Chaining** — compose skills into validated chains over the tree.

Full detail in **[ROADMAP.md](ROADMAP.md)** — generated from [`roadmap.json`](roadmap.json) (the single source); the [site](site/index.html) renders it live. Run `python3 scripts/update_site.py` after editing the roadmap or changelog.

## Changelog

### v0.1.0 — 2026-06-18
- Initial release. The Read-breadcrumb tree (`materialize` + the traversability `validate` gate); the front half — `discover` (fs→tree), `cohere` (drift report), `emit` (lossless, journaled tree-ify of a forest), `unemit` (exact undo); the decoherence `watch` writing a self-managed notification rule; the CLI; the site + Dev Log. The auto-load mechanic — Read-into-a-dir injects its layer, `cat` does not, nested doesn't load — was verified against the runtime, not asserted. 56 tests · Python 3.11+ · MIT.

## License

MIT — see [LICENSE](LICENSE).
