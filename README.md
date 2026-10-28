# skilltree

<!-- SCALABLE-PUBLISHING:AUTOGEN START (managed block — do not edit between these markers) -->

![License](https://img.shields.io/badge/license-MIT_License-blue.svg) ![Stars](https://img.shields.io/github/stars/sancovp/skilltree.svg?style=social) ![Updated](https://img.shields.io/badge/updated-2026_10_27-lightgrey.svg)

⭐ 1 stars • 🕑 Updated 2026-10-27

📦 Auto-published from the monorepo • [CHANGELOG](./CHANGELOG.md) • [sancovp/skilltree](https://github.com/sancovp/skilltree)

<!-- SCALABLE-PUBLISHING:AUTOGEN END -->

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

## Subcommands

One CLI for the whole skill-substrate toolkit — `skilltree <command> …`:

| Command | What it does |
|---|---|
| `tree <root>` | show the coordinate tree on disk (every node by its `<coord>-<name>` address) |
| `map <folder> [--write]` | render a flat folder into **one** coordinate-addressed `CLAUDE.md` (Folder Map + addressable Index + branch summaries) — progressive disclosure over a flat pile |
| `search <folder> <query> [--scope <coord>]` | FTS5/BM25 over **any** folder; `--scope` restricts to a coordinate subtree when the folder carries skilltree coordinates (a plain folder = coordinate-free search) |
| `fold <framework_dir> --into <node> --tree <root>` | **bind** a framework (its skill dir) into a volume node's `## Frameworks` tome table — idempotent, one row per framework; the manifest is the source of truth and the node's SKILL.md is regenerated from it |
| `project <root> <target> [--policy flat\|progressive] [--link absolute\|relative] [--node N]` | **deploy** a tree into a skills dir as symlinks: `progressive` surfaces root + first-layer branches (the former `link_tree`); `flat` projects a volume's tome rows + holder so every held framework auto-discovers top-level (the former nomicon-atomize). Projecting is an install, so it localizes the tree's breadcrumbs first |
| `relink <root> [--localize]` | rewrite only the breadcrumb paths: **portable** (the default and the shipped form — relative to each node's folder, no machine's path in any file) or `--localize` (absolute for this machine — the install-time step) |
| `cohere <root>` | report drift between the on-disk tree and its coherent shape |
| `emit <root> [--root-forest] [--localize]` | re-cohere in place; `--root-forest` tree-ifies a bare forest (lossless, journaled); breadcrumbs portable unless `--localize` |
| `unemit <root>` | reverse the last `emit`, byte-for-byte |
| `discover` · `validate` · `build` · `notify` · `watch` | read a tree · gate breadcrumb-resolvability · materialize from a manifest · write the notification rule · run the decoherence cron |

`map` and `search` **fold the former standalone `skillmap` / `foldersearch` / `skillsearch` seedlings into one product**: `map` uses skilltree's own coordinate code (`assign_coords` / `skill_name`, no vendored copy), and `search` is one FTS5/BM25 engine where `--scope` is the only difference between coordinate-free and tree-aware search. The `<coord>-<name>` frontmatter and the Read-breadcrumb format are preserved for backward compatibility.

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

## Papers

Two papers document the project:

- **"Flat versus Tree: Why Agent Skills Need a Graph"** — *the why.* The structural argument: a flat skill substrate starves the faculty agents actually run on; the correction is a tree traversed in `O(depth)`, not loaded in `O(#tools)`. → [`papers/flat-vs-tree.md`](papers/flat-vs-tree.md)
- **"Coordinate-Addressed Skill Trees: Progressive Disclosure on a Flat Filesystem"** — *the how.* The coordinate scheme, the Read-breadcrumb tree, the `discover`/`cohere`/`emit`/`unemit` self-coherence loop, and the runtime-verified load mechanic. → [`papers/skilltree-paper.md`](papers/skilltree-paper.md)

> arXiv submission is **pending an endorser**.

## Changelog

### v0.4.0 — 2026-10-23
- **Trees ship portable.** Every breadcrumb names its child relative to the node's folder (the folder holding the SKILL.md's `.claude/`), and the manifest stores `skill_src` relative to itself, so a materialized tree carries no machine's path and validates wherever it is copied — with no step. `materialize`, `emit` and `exchange build` take `localize=True` (`--localize`) to write absolute paths for one machine; the new `relink` rewrites only the paths, either way; `project` localizes the tree it projects (a projected tree is read through a symlink, where only an absolute path resolves). `validate` accepts both forms. 80 tests (7 new, in `tests/test_portable.py`).
- **Developed in one source home and published here.** This repository and PyPI `agent-skilltree` are the published output of SkillTree's source home; changes arrive as releases, each with a version and an entry here.
- Frontmatter quotes YAML-unsafe scalars (#1), merged after 0.3.0 and not yet released.
- The figure script writes beside itself instead of to a fixed folder; a test comment names the author by role.

### v0.3.0 — 2026-07-09
- **The tome bind ops (SkillVolume/SkillTome).** A node can now HOLD frameworks: `TreeNode.frameworks`
  rows live in the manifest and render as a generated `## Frameworks` pointer-table (`| Framework |
  What it's for | Framework skill |`) on the node's SKILL.md — regenerated by both `materialize` and
  the in-place re-cohere (`emit`), so a folded table can never be wiped or drift. New ops:
  **`fold(framework_dir, into=..., tree_root=...)`** (bind a framework into a volume — idempotent, one
  row per framework, surgical single-node rewrite) and **`project(tree, target, policy={progressive,flat},
  link={absolute,relative}, node=...)`** — ONE deployment op unifying the top-level symlink surfacing
  (`link_tree` is now a thin wrapper) with the flat auto-discoverable projection of a volume's held
  frameworks (tome rows + holder, self-clobber-guarded, relative-link-capable). `validate` grew the
  **tome-table round-trip**: manifest rows must appear in the table, every row's target must resolve,
  undeclared table rows warn. CLI: `skilltree fold [--relative]`, `skilltree project`. **Repo-portable
  tomes:** `fold(relative=True)` stores rows relative to the holder dir, so a committed tome validates
  and projects from ANY checkout — the CI flow is `emit` (localize the breadcrumbs) then `validate`.
  Fixed `--version` (the click probe needed the `agent-skilltree` distribution name). Suite →
  **70 passing** (+11 tome tests).
- Vocabulary: a branch holding frameworks is a **SkillVolume**; the overall corpus is a **SkillTome**
  ("nomicon" is the legacy alias). The table heading stays `## Frameworks` — existing table parsers
  keep working (verified against the reference atomizer end-to-end).

### v0.2.0 — 2026-06-18
- **Folded the `skillmap` / `foldersearch` / `skillsearch` seedlings into skilltree as subcommands — one product.** `skilltree map <folder> [--write]` renders a flat folder into one coordinate-addressed `CLAUDE.md`, using skilltree's **own** coordinate code (`assign_coords`/`skill_name` from `model.py`; the vendored copy is gone). `skilltree search <folder> <query> [--scope <coord>]` is **one** FTS5/BM25 engine over any folder — coordinate-free on a plain folder, coordinate-subtree-scoped when the folder carries skilltree coordinates (`foldersearch` + `skillsearch` unified; the `--scope` flag is the only difference). Added the `tree` view command. The `<coord>-<name>` frontmatter and the Read-breadcrumb format are preserved (backward compatible). Suite grew 56 → **62 tests**.

### v0.1.0 — 2026-06-18
- Initial release. The Read-breadcrumb tree (`materialize` + the traversability `validate` gate); the front half — `discover` (fs→tree), `cohere` (drift report), `emit` (lossless, journaled tree-ify of a forest), `unemit` (exact undo); the decoherence `watch` writing a self-managed notification rule; the CLI; the site + Dev Log. The auto-load mechanic — Read-into-a-dir injects its layer, `cat` does not, nested doesn't load — was verified against the runtime, not asserted. 56 tests · Python 3.11+ · MIT.

## License

MIT — see [LICENSE](LICENSE).
