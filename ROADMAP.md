# skilltree roadmap

> A navigable tree over flat skill dirs.  ·  updated 2026-06-18

## v1 — Claude Code  ·  ▸ in progress

The tree, on the one substrate whose load mechanic it exploits. Shipping.

- Read-breadcrumb tree (materialize) + traversability gate (validate)
- Front half: discover → cohere → emit → unemit (lossless, journaled)
- Decoherence watch → self-managed notification rule
- Auto-load mechanic verified against the runtime (not asserted)
- 56 tests · CLI · site + Dev Log · the Flat-vs-Tree paper

## v2 — Cross-format adapters  ·  ○ planned

Per-format adapters, NOT symlinks — the descent mechanic doesn't generalize.

- Verified: Codex resolves once at cwd; Gemini eager-loads the whole tree
- Portable foundation: SKILL.md + .agents/skills + metadata progressive-disclosure
- The index/breadcrumb skill (metadata-first routing) ports everywhere
- Codex adapter: simulate descent (scope-flatten / relaunch-at-node)
- Gemini adapter: gate the eager load (their unshipped issue #11488)

## v3 — Chaining  ·  ○ planned

Compose skills into validated chains over the tree. After cross-format.

- Sequence skills into a checkable chain
- Chains compose (a chain can chain a chain)
- Gate the chain's form, not its content

---

*The principle (from the paper's §8): the filesystem is the weakest substrate that supports a tree, so cross-tool support is not "symlink it" — each substrate needs its own emulation of the edge the platform omitted. That each tool fails differently (Codex hides too much, Gemini hides nothing) is the thesis, not a counterexample.*

*This file is generated from `roadmap.json` by `scripts/update_site.py`. Edit the JSON, not this.*
