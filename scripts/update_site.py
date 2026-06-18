#!/usr/bin/env python3
"""Regenerate everything downstream of roadmap.json + the README changelog.

  roadmap.json  ─┐
  README.md      ├─►  ROADMAP.md          (the human-readable roadmap)
  (## Changelog) ─┤    assets/roadmap.svg   (the roadmap image)
                 └─►  site/data.json       (what the website renders dynamically)

roadmap.json is the SINGLE SOURCE: ROADMAP.md, the SVG, and the site all derive from it.
Run after editing roadmap.json or the README changelog:

    python3 scripts/update_site.py
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
ROADMAP = ROOT / "roadmap.json"
README = ROOT / "README.md"
MD_OUT = ROOT / "ROADMAP.md"
SVG_OUT = ROOT / "assets" / "roadmap.svg"
DATA_OUT = ROOT / "site" / "data.json"

STATUS = {
    "done":        {"label": "✓ done",        "md": "✓ done",        "fill": "#e9f7ef", "stroke": "#16a34a", "pill": "#16a34a"},
    "in_progress": {"label": "▸ in progress", "md": "▸ in progress", "fill": "#eef4ff", "stroke": "#3b6fd4", "pill": "#3b6fd4"},
    "planned":     {"label": "○ planned",     "md": "○ planned",     "fill": "#f6f6f5", "stroke": "#c4c4bf", "pill": "#9a9a96"},
}

# The fixed prose footer for ROADMAP.md — the principle behind the phasing (on-thesis with the paper).
FOOTER = (
    "---\n\n"
    "*The principle (from the paper's §8): the filesystem is the weakest substrate that supports a "
    "tree, so cross-tool support is not \"symlink it\" — each substrate needs its own emulation of the "
    "edge the platform omitted. That each tool fails differently (Codex hides too much, Gemini hides "
    "nothing) is the thesis, not a counterexample.*\n\n"
    "*This file is generated from `roadmap.json` by `scripts/update_site.py`. Edit the JSON, not this.*\n"
)


def parse_changelog(readme_text: str) -> list[dict]:
    """Parse the `## Changelog` section: `### vX — date` + `- ` bullets."""
    m = re.search(r"^##\s+Changelog\s*$(.*?)(?=^##\s|\Z)", readme_text, re.M | re.S)
    if not m:
        return []
    body, entries, cur = m.group(1), [], None
    for line in body.splitlines():
        h = re.match(r"^###\s+(\S+)\s*(?:—|-)\s*(.+?)\s*$", line)
        if h:
            cur = {"version": h.group(1), "date": h.group(2), "changes": []}
            entries.append(cur)
        elif cur is not None and re.match(r"^\s*-\s+", line):
            cur["changes"].append(re.sub(r"^\s*-\s+", "", line).strip())
    return entries


def render_markdown(data: dict) -> str:
    """A clean ROADMAP.md from the structured source."""
    out = [f"# {data['project']} roadmap", "",
           f"> {data['tagline']}  ·  updated {data['updated']}", ""]
    for ph in data["phases"]:
        st = STATUS.get(ph["status"], STATUS["planned"])
        out.append(f"## {ph['id']} — {ph['title']}  ·  {st['md']}")
        out.append("")
        out.append(f"{ph['blurb']}")
        out.append("")
        for it in ph["items"]:
            out.append(f"- {it}")
        out.append("")
    out.append(FOOTER)
    return "\n".join(out)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(data: dict) -> str:
    phases = data["phases"]
    pad, card_w, gap, top = 40, 232, 18, 96
    card_h = 300
    width = pad * 2 + len(phases) * card_w + (len(phases) - 1) * gap
    height = top + card_h + 40
    P = []
    P.append(f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
             f'font-family="ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif">')
    P.append(f'<rect x="0" y="0" width="{width}" height="{height}" rx="14" fill="#ffffff"/>')
    P.append(f'<text x="{pad}" y="44" font-size="22" font-weight="800" fill="#15151a">{_esc(data["project"])} — roadmap</text>')
    P.append(f'<text x="{pad}" y="68" font-size="13" fill="#5e5e66">{_esc(data["tagline"])}  ·  updated {_esc(data["updated"])}</text>')
    for i, ph in enumerate(phases):
        st = STATUS.get(ph["status"], STATUS["planned"])
        x = pad + i * (card_w + gap)
        if i > 0:
            ax = x - gap
            P.append(f'<path d="M{ax-2} {top+30} h{gap+2}" stroke="#c4c4bf" stroke-width="2" '
                     f'marker-end="url(#a)" fill="none"/>')
        P.append(f'<rect x="{x}" y="{top}" width="{card_w}" height="{card_h}" rx="11" '
                 f'fill="{st["fill"]}" stroke="{st["stroke"]}" stroke-width="1.6"/>')
        P.append(f'<text x="{x+16}" y="{top+30}" font-size="12" font-weight="800" '
                 f'letter-spacing=".08em" fill="{st["pill"]}">{_esc(ph["id"])}</text>')
        P.append(f'<rect x="{x+card_w-104}" y="{top+16}" width="88" height="20" rx="10" fill="{st["pill"]}"/>')
        P.append(f'<text x="{x+card_w-60}" y="{top+30}" text-anchor="middle" font-size="10.5" '
                 f'font-weight="700" fill="#ffffff">{_esc(st["label"])}</text>')
        P.append(f'<text x="{x+16}" y="{top+58}" font-size="16" font-weight="800" fill="#15151a">{_esc(ph["title"])}</text>')
        words, line, ly = ph["blurb"].split(), "", top + 80
        for w in words:
            if len(line) + len(w) > 30:
                P.append(f'<text x="{x+16}" y="{ly}" font-size="11.5" fill="#5e5e66">{_esc(line)}</text>')
                line, ly = w, ly + 16
            else:
                line = (line + " " + w).strip()
        if line:
            P.append(f'<text x="{x+16}" y="{ly}" font-size="11.5" fill="#5e5e66">{_esc(line)}</text>')
        iy = ly + 26
        for it in ph["items"]:
            txt = it if len(it) <= 34 else it[:33] + "…"
            P.append(f'<text x="{x+16}" y="{iy}" font-size="11" fill="#15151a">•  {_esc(txt)}</text>')
            iy += 20
    P.append('<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" '
             'orient="auto"><path d="M0 0 L10 5 L0 10 z" fill="#c4c4bf"/></marker></defs>')
    P.append('</svg>')
    return "\n".join(P) + "\n"


def main() -> int:
    data = json.loads(ROADMAP.read_text(encoding="utf-8"))
    changelog = parse_changelog(README.read_text(encoding="utf-8")) if README.exists() else []

    MD_OUT.write_text(render_markdown(data), encoding="utf-8")
    SVG_OUT.parent.mkdir(parents=True, exist_ok=True)
    SVG_OUT.write_text(render_svg(data), encoding="utf-8")
    site_data = {**data, "changelog": changelog}
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    DATA_OUT.write_text(json.dumps(site_data, indent=2), encoding="utf-8")

    print(f"✓ wrote {MD_OUT.relative_to(ROOT)}")
    print(f"✓ wrote {SVG_OUT.relative_to(ROOT)} ({len(data['phases'])} phases)")
    print(f"✓ wrote {DATA_OUT.relative_to(ROOT)} ({len(changelog)} changelog entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
