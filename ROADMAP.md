# skilltree roadmap

## v1 — Claude Code (shipping)

A navigable tree over flat `.claude/skills`, with the front half (`discover` / `cohere` /
`emit` / `unemit`) and the decoherence watcher. **The descent mechanic is Claude-Code-specific
by design** — it exploits Claude Code's *dynamic-load-on-Read-into-a-directory* behavior
(verified against the runtime). This is the most capable target and the one the "Flat vs Tree"
paper is about.

## v2 — cross-format (the first update, after publish)

**Not symlinks.** We verified (2026-06) that the core mechanic does **not** generalize:

| | dynamic-load-on-entry | failure mode without it |
|---|---|---|
| **Claude Code** | yes (Read triggers; `cat` doesn't) | — |
| **OpenAI Codex** | no — resolves once at startup, **stops at cwd** | "descend by reading" is a no-op |
| **Gemini CLI** | no — **eager-loads the whole subtree** at startup | nesting hides nothing (the bloat we kill); lazy-gating is unshipped issue `#11488` |

So cross-format is **per-format adapters**, not one trick:
- **Codex adapter** — simulate descent out-of-band (flatten the relevant subtree's skills into the
  launch scope, or relaunch with cwd at the node).
- **Gemini adapter** — the inverse: gate the eager load (effectively building their unshipped
  just-in-time-context feature).

**What IS portable today** (so the adapters have a foundation): `SKILL.md` + the `.agents/skills`
directory convention + progressive-disclosure-of-metadata is a genuine cross-tool standard (Codex,
Gemini, Cursor, …). Individual skill *content* ports as-is; only the *navigable-tree-via-descent
runtime* is substrate-specific. Re-expressing skilltree's value as a portable **index/breadcrumb
skill** (metadata-first routing) + a per-substrate descent emulation is the v2 shape.

> Note: `AGENTS.md` is the cross-tool *instructions* standard (OpenAI/Google/Cursor/…), but Claude
> Code is the one tool that reads `CLAUDE.md` instead. The naming is `.agents/skills` (plural).

## v3 — the chaining system

Compose skills into validated chains over the tree. Deferred until cross-format lands.

---

*The principle (from the paper's §8): the filesystem is the weakest substrate that supports a tree,
so cross-tool support is not "symlink it" — each substrate needs its own emulation of the edge the
platform omitted. That each tool fails differently (Codex hides too much, Gemini hides nothing) is
the thesis, not a counterexample.*
