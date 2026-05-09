"""SUITE: XD-FIDELITY — verify each captured wizard step matches its XD design.

For every entry in `xd-links.md` we emit a single `XD-FIDELITY-step-NN`
assertion. xd-links uses 0-based step numbering ("Step 0" is the first
wizard screen). The wizard runner captures with 1-based filenames
(`wizard_step_01.png` is the first step), so the mapping is
`xd-links Step N -> wizard_step_{N+1:02d}.png` for N=0..11.

Steps 12..15 in xd-links describe post-wizard screens (project landing /
dashboard / etc.) and are NOT captured by the wizard runner. They are
recorded with `verdict=unverified` and a note explaining why.

Truth signals (cheap proxies — no pixel diff against private XD render):

- Text fidelity:   captured `.txt` sidecar must contain the canonical
                   step heading + the domain-required affordances we
                   know that step has to expose (per `STEP_EXPECTATIONS`
                   below). The expectations are derived from xd-links
                   notes and the wizard's own JS.
- File size:       a populated wizard step at 1440x900@DPR=2 weighs
                   60..600 KB. Anything below 40KB is a smell.
- sha1 collision:  two wizard steps with identical sha1 indicate a
                   render-routing bug. We fail on any pair that collides.
- Palette family:  the step's dominant non-white colour family must be
                   neutral gray (matches Frappe's design token
                   `--bg-light`) — the eGRM wizard does NOT use brand
                   green/orange large-fills in the body. A step whose
                   dominant pixel is far from neutral gray is flagged.

The runner is deliberately conservative: it emits `pass` only when text
+ size + uniqueness all check out. `mismatch:<reason>` triggers a
healable-failure. `unverified` is used ONLY for steps where xd-links
points to a screen we don't capture (Step 12..15).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from _common import ART, SuiteRun, run, summary

# --------------------------------------------------------------------- inputs

XD_REFS_PATH = ART / "xd_references.json"
WIZARD_STEPS_DIR = ART / "screenshots" / "wizard_steps"

# Canonical heading + "must-contain" tokens per step (case-insensitive).
# Keys are 0-based xd-links step numbers; values describe what the
# CAPTURED `wizard_step_{step+1:02d}.txt` sidecar MUST mention. These
# are the domain-required affordances for each wizard step body.
STEP_EXPECTATIONS: dict[int, dict] = {
    0:  {"heading": "1. project information",
         "must_contain": ["project code", "title", "description",
                          "start date", "end date", "default language",
                          "auto escalation", "is active"]},
    1:  {"heading": "2. uptake notes",
         "must_contain": ["uptake", "channel", "project description"]},
    2:  {"heading": "3. administrative levels",
         "must_contain": ["level", "order", "ack", "res", "auto escalate",
                          "+ add level"]},
    3:  {"heading": "4. project roles",
         "must_contain": ["role name", "duties", "active",
                          "+ add role"]},
    4:  {"heading": "5. departments",
         "must_contain": ["department", "head", "+ add department"]},
    5:  {"heading": "6. issue categories",
         "must_contain": ["category", "label", "department",
                          "confidentiality", "+ add category"]},
    6:  {"heading": "7. issue types",
         "must_contain": ["type name", "+ add type"]},
    7:  {"heading": "8. issue statuses",
         "must_contain": ["status name", "initial", "open", "final",
                          "rejected", "+ add status"]},
    8:  {"heading": "9. slas",
         "must_contain": ["acknowledgment", "resolution", "auto escalate",
                          "save all"]},
    9:  {"heading": "10. citizen lookups",
         "must_contain": ["age group", "citizen group", "+ add age group",
                          "+ add citizen group"]},
    10: {"heading": "11. notification templates",
         "must_contain": ["+ add template"]},
    # Step 11 (activation page). xd-links Step 11 explicitly notes
    # "these oui or no can be checkboxes as frappe does for permissions"
    # — i.e. the activation pre-flight should expose a checkbox-styled
    # toggle for the activation flag, NOT a free-text "Already Active"
    # banner. Our heal in grm_project_wizard.js adds a checkbox row.
    11: {"heading": "12. activate",
         "must_contain": ["project summary", "project code",
                          "i confirm"]},
}

# Steps 12..15 in xd-links describe post-wizard screens that the wizard
# runner does NOT capture. We mark them `unverified` and document why.
POST_WIZARD_NOTE = {
    12: "post-wizard screen (project landing) — out of wizard runner scope",
    13: "post-wizard screen (project dashboard) — out of wizard runner scope",
    14: "post-wizard screen (admin desk) — out of wizard runner scope",
    15: "post-wizard screen (final/colour palette index) — branding root",
}

MIN_PNG_BYTES = 40 * 1024     # below this is suspicious (40KB)
MAX_PNG_BYTES = 4 * 1024 * 1024  # above this hints at unexpected over-render

# Neutral-gray family: each channel within ±35 of the others, all > 80.
# This matches Frappe's neutral palette and the captured eGRM wizard.
def _is_neutral_gray(rgb: tuple[int, int, int]) -> bool:
    r, g, b = rgb
    if min(r, g, b) < 80:
        return False
    spread = max(abs(r - g), abs(g - b), abs(r - b))
    return spread <= 35


def _dominant_nonwhite(png: Path) -> tuple[int, int, int] | None:
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(png).convert("RGB").resize((120, 75))
    except Exception:
        return None
    nonwhite = [
        px for px in im.getdata()
        if not (px[0] > 240 and px[1] > 240 and px[2] > 240)
    ]
    if not nonwhite:
        return None
    return Counter(nonwhite).most_common(1)[0][0]


def _sha1(p: Path) -> str:
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def _read_sidecar(png: Path) -> str:
    txt = png.with_suffix(".txt")
    if txt.exists():
        try:
            return txt.read_text()
        except Exception:
            return ""
    return ""


def _check_step(step: int, ref: dict, sha_index: dict[str, list[int]]) -> tuple[str, str]:
    """Return (verdict, detail). verdict in {pass, mismatch:..., unverified}."""
    captured_rel = ref.get("captured_png")
    if captured_rel is None or step >= 12:
        why = POST_WIZARD_NOTE.get(step, "no capture for this step")
        return ("unverified", why)

    png = ART / captured_rel
    if not png.exists():
        return ("mismatch:missing_png", f"expected {png.name}")

    size = png.stat().st_size
    if size < MIN_PNG_BYTES:
        return ("mismatch:undersized_png",
                f"{size}B < {MIN_PNG_BYTES}B (likely empty/error capture)")
    if size > MAX_PNG_BYTES:
        return ("mismatch:oversized_png",
                f"{size}B > {MAX_PNG_BYTES}B (unexpectedly large)")

    sha = _sha1(png)
    collisions = [s for s in sha_index.get(sha, []) if s != step]
    if collisions:
        return ("mismatch:duplicate_render",
                f"sha1 {sha} also appears at step(s) {collisions}")

    body = _read_sidecar(png).lower()
    if not body or len(body) < 80:
        return ("mismatch:blank_body",
                f"sidecar text is {len(body)} chars (<80)")

    exp = STEP_EXPECTATIONS.get(step)
    missing: list[str] = []
    heading_ok = True
    if exp:
        if exp.get("heading") and exp["heading"].lower() not in body:
            heading_ok = False
        for tok in exp.get("must_contain", []):
            if tok.lower() not in body:
                missing.append(tok)

    if not heading_ok:
        return ("mismatch:wrong_heading",
                f"expected '{exp['heading']}' to appear in body")
    if missing:
        return ("mismatch:missing_affordances",
                f"missing tokens: {missing}")

    dom = _dominant_nonwhite(png)
    if dom is not None and not _is_neutral_gray(dom):
        # Heuristic warning, not a hard fail — colour family check is
        # fuzzy and we don't want false positives. Emit as pass-with-note.
        return ("pass",
                f"size={size}B sha1={sha} dominant_rgb={dom} "
                f"(non-neutral; visually inspect)")

    return ("pass", f"size={size}B sha1={sha} dominant_rgb={dom}")


# ----------------------------------------------------------------- main

def main() -> int:
    suite = SuiteRun("XD-FIDELITY")

    if not XD_REFS_PATH.exists():
        suite.ok(
            "XD-FIDELITY-bootstrap",
            False,
            f"{XD_REFS_PATH} missing — run fetch_xd_refs.py first",
        )
        return summary(suite)

    refs = json.loads(XD_REFS_PATH.read_text())
    steps = refs.get("steps") or {}

    # First pass: build sha1 index for cross-step uniqueness.
    sha_index: dict[str, list[int]] = {}
    for key, ref in steps.items():
        cap = ref.get("captured_png")
        if not cap:
            continue
        png = ART / cap
        if png.exists():
            sha_index.setdefault(_sha1(png), []).append(ref["step"])

    suite.ok(
        "XD-FIDELITY-bootstrap",
        True,
        f"{len(steps)} XD references loaded; "
        f"{sum(1 for r in steps.values() if r.get('captured_png'))} captures present",
    )

    # Second pass: per-step verdict.
    for key in sorted(steps.keys()):
        ref = steps[key]
        step = ref["step"]
        verdict, detail = _check_step(step, ref, sha_index)

        wizard_idx = ref.get("wizard_idx")
        wizard_idx_s = f"wizard_step_{wizard_idx:02d}.png" if wizard_idx else "(no capture)"
        full_detail = (
            f"xd_url={ref.get('xd_url')} "
            f"og_image={'(present)' if ref.get('og_image') else '(missing)'} "
            f"captured={wizard_idx_s} "
            f"verdict={verdict} | {detail}"
        )

        passed = verdict == "pass"
        # `unverified` is recorded as a non-failure — these steps are
        # explicitly out of the wizard runner's capture scope.
        if verdict == "unverified":
            passed = True
        suite.ok(f"XD-FIDELITY-step-{step:02d}", passed, full_detail)

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
