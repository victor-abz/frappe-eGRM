"""One-shot helper: fetch XD metadata for every screen in xd-links.md.

Adobe XD share pages render their public OG/Twitter metadata only when a
bot-style User-Agent is used. The `og:title`/`og:description` are
project-scoped (same for every screen) but the `og:image` carries a
per-screen `component_id` that uniquely identifies the design canvas — we
treat that image URL as the per-step XD reference.

Output: /Users/victor/egrm/aqe-screenshots/aqe-full-suite/xd_references.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

XD_LINKS = Path("/Users/victor/egrm/apps/egrm/docs/superpowers/plans/xd-links.md")
ART = Path("/Users/victor/egrm/aqe-screenshots/aqe-full-suite")
SHOTS_DIR = ART / "screenshots" / "wizard_steps"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 facebookexternalhit/1.1"
)

URL_RE = re.compile(
    r"Step\s+(\d+)\s+(https?://xd\.adobe\.com/view/[A-Za-z0-9\-]+/screen/[A-Za-z0-9\-]+)"
)
COLOR_RE = re.compile(
    r"Color\s*Palette\s*(https?://xd\.adobe\.com/view/[A-Za-z0-9\-]+/?)"
)
META_RE = re.compile(
    r'(og:(?:title|description|image|url))"\s*content="([^"]+)"'
)


def parse_xd_links() -> tuple[list[tuple[int, str]], str]:
    raw = XD_LINKS.read_text()
    steps = [(int(n), url) for n, url in URL_RE.findall(raw)]
    color_match = COLOR_RE.search(raw)
    color_root = color_match.group(1) if color_match else ""
    return steps, color_root


def fetch_meta(url: str) -> dict:
    req = Request(url, headers={"User-Agent": UA})
    out: dict = {"og_title": None, "og_description": None, "og_image": None,
                 "og_url": None, "fetch_ok": False, "fetch_error": None}
    try:
        with urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        out["fetch_error"] = f"{type(e).__name__}: {e}"
        return out
    out["fetch_ok"] = True
    for key, val in META_RE.findall(html):
        # html-decode minimal entities
        val = (val.replace("&amp;", "&").replace("&quot;", '"')
                  .replace("&#x2F;", "/").replace("&#39;", "'"))
        if key == "og:title":
            out["og_title"] = val
        elif key == "og:description":
            out["og_description"] = val
        elif key == "og:image":
            out["og_image"] = val
        elif key == "og:url":
            out["og_url"] = val
    return out


def captured_for_step(step: int) -> str | None:
    """xd-links uses 0-based; capture indices are 1-based.

    Step 0..11 -> wizard_step_01..12
    Step 12..15 are post-wizard screens (project landing/dashboard) and
    are not captured by the wizard runner.
    """
    if step > 11:
        return None
    idx = step + 1
    p = SHOTS_DIR / f"wizard_step_{idx:02d}.png"
    return f"screenshots/wizard_steps/{p.name}" if p.exists() else None


def main() -> int:
    steps, color_root = parse_xd_links()
    print(f"Found {len(steps)} XD step URLs in xd-links.md")
    refs: dict = {
        "_doc": (
            "Per-step XD references. Numbering follows xd-links.md "
            "(0-based). wizard_idx is 1-based to match captured PNG "
            "filenames (wizard_step_NN.png)."
        ),
        "color_palette_root": color_root,
        "steps": {},
    }
    for step, url in steps:
        print(f"  fetching Step {step} ...")
        meta = fetch_meta(url)
        refs["steps"][f"step_{step:02d}"] = {
            "step": step,
            "wizard_idx": (step + 1) if step <= 11 else None,
            "xd_url": url,
            "captured_png": captured_for_step(step),
            **meta,
        }
    out = ART / "xd_references.json"
    out.write_text(json.dumps(refs, indent=2))
    n_ok = sum(1 for v in refs["steps"].values() if v.get("fetch_ok"))
    n_with_img = sum(1 for v in refs["steps"].values() if v.get("og_image"))
    print(f"Wrote {out} — fetch_ok={n_ok}/{len(steps)}, og_image={n_with_img}/{len(steps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
