#!/usr/bin/env python3
"""
Figure 1 — Upfront context cost: flat O(#tools) vs. tree O(depth).

The hero figure for "Flat versus Tree." It is a MODEL, not a fresh measurement,
but every constant is anchored to a verified figure in the paper:

  flat(N)  = c_schema * N
      c_schema = 150 tokens per tool definition, chosen so that flat(1000) = 150,000 —
      exactly Anthropic's reported upfront cost for an agent connected to many tools
      ("...process hundreds of thousands of tokens before reading a request";
       "150,000 tokens", Code execution with MCP, 2025).

  tree(N)  = c_root + c_entry * b * ceil(log_b N)
      To reach one tool among N you DESCEND a b-ary tree: at each of d = ceil(log_b N)
      levels you read the current node's menu (b one-line child summaries). Constants:
        c_root  = 200   fixed root-menu overhead
        c_entry = 30    tokens per menu line (coordinate + one-line summary)
        b       = 5     menu fan-out
      => tree(1000) ~= 950 tokens, the same ORDER as Anthropic's measured on-demand
         cost ("2,000 tokens", a 98.7% reduction). Both Anthropic points are plotted
         as real markers; the tree CURVE is the model.

The robust content is the ASYMPTOTICS — flat is linear, tree is logarithmic — and the
crossover: below a handful of tools the flat load is trivially cheaper (which is why
small toolsets feel fine and nobody noticed); past it, the linear curve explodes while
the tree stays nearly flat. The exact crossover location depends on the constants above;
the divergence does not.
"""
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, FuncFormatter

# --- model constants (all stated in the docstring / caption) ---
C_SCHEMA = 150      # tokens per tool definition, flat upfront
C_ROOT   = 200      # tree: fixed root overhead
C_ENTRY  = 30       # tree: tokens per menu line
B        = 5        # tree: branching factor (menu fan-out)

def flat(n):
    return C_SCHEMA * n

def tree(n):
    n = np.asarray(n, dtype=float)
    depth = np.ceil(np.log(n) / np.log(B))
    depth = np.maximum(depth, 0)
    return C_ROOT + C_ENTRY * B * depth

# --- crossover: smallest integer N where flat >= tree ---
cross_n = next(n for n in range(1, 100000) if flat(n) >= tree(np.array([n]))[0])
cross_y = flat(cross_n)

# --- data ---
N = np.unique(np.round(np.logspace(0, math.log10(5000), 400)).astype(int))
N = N[N >= 1]
y_flat = flat(N)
y_tree = tree(N)

# --- style ---
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 11,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#333333",
})
COL_FLAT = "#c0392b"   # the tax
COL_TREE = "#1f6f4a"   # the fix
COL_ANCH = "#2c3e50"   # anchors

fig, ax = plt.subplots(figsize=(7.2, 4.6))

ax.plot(N, y_flat, color=COL_FLAT, lw=2.4, label=r"flat — load all schemas upfront  $O(\#\mathrm{tools})$", zorder=3)
ax.plot(N, y_tree, color=COL_TREE, lw=2.4, label=r"tree — descend on demand  $O(\mathrm{depth})$", zorder=3)

# crossover
ax.scatter([cross_n], [cross_y], s=42, color="#000000", zorder=5)
ax.annotate(f"crossover ≈ {cross_n} tools\n(below this, flat is trivially cheaper —\nwhy small toolsets feel fine)",
            xy=(cross_n, cross_y), xytext=(1.6, 2600),
            fontsize=8.6, color="#222222", ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color="#777777", lw=0.8))

# Anthropic verified anchors at N=1000
ax.scatter([1000], [150000], s=46, marker="o", color=COL_ANCH, zorder=6)
ax.annotate("Anthropic, measured:\n150,000 tokens upfront",
            xy=(1000, 150000), xytext=(110, 240000),
            fontsize=8.6, color=COL_ANCH, ha="left", va="center",
            arrowprops=dict(arrowstyle="-", color=COL_ANCH, lw=0.8))
ax.scatter([1000], [2000], s=46, marker="s", color=COL_ANCH, zorder=6)
ax.annotate("Anthropic, measured:\n2,000 tokens on-demand  (−98.7%)",
            xy=(1000, 2000), xytext=(5200, 9000),
            fontsize=8.6, color=COL_ANCH, ha="right", va="center",
            arrowprops=dict(arrowstyle="-", color=COL_ANCH, lw=0.8))

# the gap bracket at N=1000
ax.annotate("", xy=(1000, 150000), xytext=(1000, 2000),
            arrowprops=dict(arrowstyle="<->", color="#999999", lw=1.0, ls=(0, (4, 3))))
ax.text(760, 17000, "the tax\nat 1000 tools", fontsize=8, color="#777777", ha="right", va="center", style="italic")

ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlim(1, 6000)
ax.set_ylim(80, 4e5)
ax.set_xlabel("number of tools / skills available  (N)")
ax.set_ylabel("context tokens to reach one tool")
ax.set_title("Upfront context cost: flat $O(\\#\\mathrm{tools})$ vs. tree $O(\\mathrm{depth})$", fontsize=12.5, pad=12)

def _kfmt(x, _):
    if x >= 1000:
        return f"{x/1000:g}k"
    return f"{x:g}"
ax.xaxis.set_major_formatter(FuncFormatter(_kfmt))
ax.yaxis.set_major_formatter(FuncFormatter(_kfmt))
ax.grid(True, which="major", color="#e6e6e6", lw=0.6, zorder=0)
ax.grid(True, which="minor", color="#f2f2f2", lw=0.4, zorder=0)

leg = ax.legend(loc="lower right", frameon=True, framealpha=0.95, edgecolor="#cccccc", fontsize=9.2)
leg.get_frame().set_linewidth(0.7)

cap = ("Model. flat(N)=150·N  (150 tok/def → 150k at N=1000, Anthropic's reported upfront cost);  "
       "tree(N)=200+30·5·⌈log₅N⌉  (root + menu-entries × fan-out × depth).  "
       "Markers = Anthropic's two measured points (150k upfront, 2k on-demand). "
       "Asymptotics (linear vs logarithmic) are the claim; the crossover location depends on the stated constants.")
fig.text(0.5, -0.04, cap, ha="center", va="top", fontsize=6.8, color="#555555", wrap=True)

fig.tight_layout()
out = "/Users/isaacwr/fable_test/SSRI/ship/figures/figure1_crossover"
fig.savefig(out + ".svg", bbox_inches="tight", pad_inches=0.18)
fig.savefig(out + ".png", dpi=200, bbox_inches="tight", pad_inches=0.18)
print(f"crossover at N={cross_n} (flat={flat(cross_n):.0f}, tree={tree(np.array([cross_n]))[0]:.0f})")
print(f"flat(1000)={flat(1000):.0f}  tree(1000)={tree(np.array([1000]))[0]:.0f}")
print("wrote", out + ".svg", "and", out + ".png")
