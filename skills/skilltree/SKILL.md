---
name: skilltree
description: "WHAT: turn a flat .claude/skills folder (or any folder of skills) into a walkable coordinate-addressed tree so the model loads one layer at a time instead of the whole pile - the skilltree CLI (discover, cohere, emit, unemit, map, search, fold, project, validate, watch). WHEN: when the user mentions skilltree, skill tree, too many skills, skills all load at once, organize/structure my skills, progressive disclosure for skills, tree-ify a flat skills folder, or a skills folder has grown past the point where tool selection degrades (any of)."
---

# skilltree — walk the tree, never load the pile

The problem this solves: the platform auto-loads `.claude/skills` one layer
deep, so at scale EVERY skill lands in context EVERY turn and tool selection
degrades. skilltree imposes a coordinate-addressed tree on that flat substrate
using the three levers the runtime leaves open: **path = coordinate**
(`0 -> 0.1 -> 0.1.1`), **depth = gate** (a nested `.claude` never auto-loads,
so deeper nodes stay out of context until entered), **Read = edge** (the Read
tool injects a directory's layer; a shell `cat` injects nothing).

## Setup (you do this yourself — the user never touches pip)

Check, and install if missing:

```bash
skilltree --help >/dev/null 2>&1 || pip install agent-skilltree
```

## The commands

| Command | What it does |
|---|---|
| `skilltree tree <root>` | show the coordinate tree on disk |
| `skilltree cohere <root>` | report drift between reality and the coherent shape (a bare forest, stale breadcrumbs, flat drops) |
| `skilltree emit <root> [--root-forest]` | re-cohere in place; `--root-forest` tree-ifies a flat forest (lossless — every move journaled) |
| `skilltree unemit <root>` | reverse the last emit, byte-for-byte |
| `skilltree map <folder> [--write]` | render ANY flat folder as one coordinate-addressed index (progressive disclosure over a pile) |
| `skilltree search <folder> <query> [--scope <coord>]` | FTS5/BM25 retrieval; `--scope` restricts to a coordinate subtree |
| `skilltree fold <framework_dir> --into <node> --tree <root>` | bind a framework into a volume node's tome table (idempotent) |
| `skilltree project <root> <target> [--policy flat\|progressive]` | deploy a tree into a skills dir as symlinks |
| `skilltree validate <root>` | gate: every breadcrumb must resolve |
| `skilltree watch <root>` | the decoherence cron — a drifted tree announces itself |

## The one law that makes descent work

Breadcrumbs instruct you to **use the Read tool** on a child's SKILL.md — that
injects the child's layer. A shell `cat` of the same file injects NOTHING (the
bytes arrive, the skill does not load). Never descend with `cat`.

## The lowest-cost first run (on the user's own skills)

```bash
skilltree cohere ~/.claude/skills   # see the drift before changing anything
skilltree emit ~/.claude/skills --root-forest   # tree-ify (reversible: unemit)
```

## Going deeper

The full mechanics (verified runtime table, file geometry, invariants, source
`path:line` map) are in this repo: `README.md`, `papers/skilltree-paper.md`,
and `papers/flat-vs-tree.md`. Read them from the plugin checkout when the user
asks how it works under the hood.
