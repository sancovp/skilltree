# Coordinate-Addressed Skill Trees: Progressive Disclosure on a Flat Filesystem

**Isaac Wostrel-Rubin** · Independent researcher · ORCID [0009-0003-0219-0506](https://orcid.org/0009-0003-0219-0506)
isaacwrubin@gmail.com · github.com/sancovp · Working paper, June 2026

## Abstract

A companion paper argues that agent operation is graph-shaped and that the prevailing skill substrate—a flat directory of skills, each disclosing only its own files—starves it.[^why] This paper is the construction. It specifies and implements a coordinate-addressed tree over an ordinary skill directory, on a substrate (the filesystem, as exposed to a coding agent) that provides no first-class edges. The tree emulates the two things a graph would supply natively: **identity**, via a hierarchical coordinate (`0.2.1`) assigned to every node, and **edges**, via *breadcrumbs*—instructions, embedded in each node, to load a specific child through the one operation that actually injects it into the model's context. Around this we build retrieval that survives the flattening (internal nodes carry a summary of their subtree, so a query for a leaf still finds the branch that leads to it) and a self-coherence loop (`discover`/`cohere`/`emit`/`unemit`) that reconstructs, audits, repairs, and losslessly reverts the on-disk structure. The whole thing is one MIT-licensed tool with a passing test suite; nothing here required a new substrate, only the disciplined use of the weakest one that works. The contribution is not an algorithm—the pieces are commodity—it is that the structure, and its maintenance, exist at all on a substrate that offers neither.

## 1. The problem this builds on

A coding agent equipped with a large corpus of skills faces a substrate that is flat by construction: the skills sit in a directory, each is a self-contained unit, and the platform's loader reads metadata for all of them and the body of none until one is triggered. There is no way for one skill to point *into* another, more specific one—no edge—so a corpus of hundreds of skills is a forest of disconnected nodes precisely at the scale where navigation matters. The companion paper develops why this is costly: if the agent's operation is a flow over the structure of its context, a structureless substrate forces the agent to reconstruct the missing paths at every step.[^why] Here we take that as given and ask the constructive question: on the substrate we actually have, what is the cheapest thing that restores the structure—and can it maintain itself, since a structure the platform will not maintain decays back to the flat forest it replaced?

## 2. The construction: coordinate as identity, breadcrumb as edge

A graph database would give each node a stable identity and each relationship a first-class, traversable edge. The filesystem gives neither. The tree emulates both.

**Identity** is a hierarchical coordinate. The root is `0`; its children are `0.1`, `0.2`, …; their children `0.1.1`, and so on. A node's coordinate is its address and, as §4 shows, also its retrieval scope. Coordinates are assigned by a single pass over the directory tree (`assign_coords`, `src/skilltree/model.py:70`), and the assignment is the *one* canonical source of the scheme—every other module reads it rather than re-deriving it.

**Edges** are breadcrumbs. Each non-leaf node's body carries, for every child, a line of the exact form

```
- 0.1-A (cor): Read `…/domain/A/.claude/skills/0.1-A/SKILL.md`
```

The breadcrumb names the child's coordinate and the single operation that loads it. A coordinate stands in for node identity; a breadcrumb stands in for a directed edge. Both are emulations of what a graph would hold natively, and the rest of the system is what it takes to make the emulation behave.

## 3. Materialization: the tree on the filesystem

Materialization writes the tree to disk so that exactly one node—the root—auto-loads, and every other node loads only when its breadcrumb is followed. Each node is a plain directory carrying its own one-skill `.claude/`; the breadcrumb emitter (`_write_node`, `src/skilltree/materialize.py:36`) writes each node's body with an index summary (§4) and the descend block (its out-edges). The breadcrumb's verb is fixed to the model's `Read` operation, never a shell read (`_CRUMB`, `materialize.py:25`); §6 explains why that distinction is load-bearing and not cosmetic.

```
domain/.claude/skills/0-domain/SKILL.md          # root — the only node that auto-loads
domain/A/.claude/skills/0.1-A/SKILL.md           # child  — loaded only when Read
domain/A/A1/.claude/skills/0.1.1-A1/SKILL.md     # grandchild — one level deeper
```

This is progressive disclosure performed by the act of reading: entering a node loads exactly its layer—its own content plus the breadcrumbs to its children—and nothing below it. The agent descends to the coordinate it needs rather than loading the corpus.

## 4. Retrieval that survives flattening

A flat list of leaves is searchable but unnavigable: a query that matches a deep skill returns the skill, not the path to it, and the agent that has not loaded the path cannot follow it. Two mechanisms recover navigability.

**Internal-node summaries.** Each non-leaf node's body carries an *index summary* composed from its subtree's own vocabulary (`compose_summary`, `model.py`): "opens to 2 branches: A (cor), B (ac); reachable below: A, A1, A2, B." A query about a descendant therefore retrieves the branch that leads to it, because the branch advertises what lies under it. Retrievability that a flat list of leaves loses is restored at every internal node.

**Coordinate-scoped search.** A retrieval index (SQLite FTS5 / BM25) ranks nodes by relevance; because every node carries its coordinate, the same index supports restricting a query to a coordinate subtree—rank only within `0.2` and its descendants. The coordinate is simultaneously the address and the search scope. Unscoped, the search is an ordinary full-corpus retrieval over any folder; scoped, it is navigation within a branch. One engine, one flag.

## 5. Coherence: the structure maintains itself

A structure the platform will not maintain must maintain itself, or it decays. Four operations close that loop.

- **`discover`** (`src/skilltree/cohere.py:117`) reconstructs the on-disk tree from reality alone, independent of any manifest—what is actually there, not what a record claims.
- **`cohere`** (`cohere.py:152`) reports the drift between that reality and the engineered shape: a bare (unrooted) forest, a stale breadcrumb, a coordinate that no longer matches its position, a skill dropped in flat.
- **`emit`** (`cohere.py:261`) re-coheres in place. Given a flat forest it *tree-ifies* it: it relocates each skill—with all of its files, resolving any symlink to a served source—into a nested node and writes the edges, **journaling every move** so that
- **`unemit`** (`cohere.py:339`) restores the prior state byte-for-byte.

A scheduled check (`write_notifications`/`watch`, `cohere.py:430`/`:448`) writes its verdict into a single managed rule, so a decohered tree announces itself in every subsequent session rather than rotting silently. The algorithms are commodity—tree walks, set differences, a journal. The contribution is that the maintenance exists at all, on a substrate that provides none of it.

## 6. The runtime load semantics the construction depends on

The emulation rests on three facts about how the target runtime loads context. Each was verified directly—observed as a state-change in the live skill manifest, by planting a marker skill and watching whether it entered the model's tool surface under each access pattern—not asserted.

| Observation | Result |
|---|---|
| A `.claude/skills` nested *below* the directory in scope | **not** auto-loaded |
| Reading a file in a directory with the `Read` tool | injects *that directory's* layer, one level; ancestors load, descendants do not |
| A shell `cat` of the *same* file | injects **nothing** |

The first row is why a depth-one corpus is a flat forest: depth is invisible until entered, so the platform enforces the flatness. The second is why a tree of plain directories is traversable at all: entering a node loads exactly its layer. The third is a correctness condition on the emulation—the breadcrumb must invoke the `Read` *tool*, not a byte read, or the edge silently fails to load and is therefore not an edge. The validator enforces exactly this: every non-leaf node must carry a `Read` breadcrumb for each child, and every breadcrumb path must resolve to a real file (`src/skilltree/validate.py:60`). These are properties of the tested runtime, not claims about filesystems in general.

## 7. Status and limitations

The construction is implemented as one MIT-licensed tool (`skilltree`, github.com/sancovp/skilltree; v0.2.0, 62 tests passing) whose `tree`/`map`/`search` subcommands expose the construction described here. The claims here are about mechanism and about observed runtime behavior, not about end-to-end task performance: this paper does not measure that a coordinate tree improves an agent's success rate over a flat corpus on arbitrary tasks. That is the benchmark the companion paper specifies and neither paper yet reports.[^why] The cost argument is asymptotic—per-step context grows with depth, not with corpus size—and its constants are implementation-dependent. The coordinate scheme is a tree; cross-branch relationships a general graph would express (a skill that is relevant under two parents) are represented only by placement, which is the honest limit of a filesystem emulation and the point at which a graph substrate stops being optional.

## 8. Why a tree, and what is above it

The tree is not the destination; it is the weakest substrate that supports the structure, chosen because it runs today with no dependencies a terminal-capable operator does not already have. A graph with first-class typed relationships would make identity and edges native rather than emulated, and would express the cross-branch relationships §7 cannot.[^kg] Stated against the companion paper's frame: if an agent's operation is a flow over the structure of its context, then materializing that structure on disk is the runnable first step toward an agent whose structure *is* its substrate. This paper builds the first step and is candid that it is the first step; the soundness and graph layers above it are out of scope here.

---

## Notes
[^why]: Isaac Wostrel-Rubin, "Flat versus Tree: Why Agent Skills Need a Graph," working paper, 2026 (companion to this paper).
[^kg]: Aidan Hogan et al., "Knowledge Graphs," *ACM Computing Surveys* 54, no. 4, art. 71 (2021), doi:10.1145/3447772, §3.4 (reification of relations to first-class objects).

## Bibliography
- Hogan, Aidan, et al. "Knowledge Graphs." *ACM Computing Surveys* 54, no. 4, art. 71 (2021). doi:10.1145/3447772.
- Wostrel-Rubin, Isaac. "Flat versus Tree: Why Agent Skills Need a Graph." Working paper, 2026.
- Wostrel-Rubin, Isaac. *skilltree.* MIT-licensed software repository, github.com/sancovp/skilltree, 2025–2026.
