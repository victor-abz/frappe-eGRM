"""Render REPORT.json + per-suite *.json into a single REPORT.html.

This is the human-visualisable artefact promised in the v2 charter. It
embeds every captured PNG inline next to its assertion, runs the same
content classifier the UI runner uses against any sidecar `.txt` file,
and flags an image RED if its body text matches a known error
signature (e.g. the "Not permitted" dialog the user rejected v1 over).

Designed to be self-contained: no external CSS/JS, opens cleanly in any
browser by `file://` URL, and works whether you run it from the CLI or
have `run_full_suite.py` invoke it as the last step.
"""
from __future__ import annotations

import base64
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ART = Path("/Users/victor/egrm/aqe-screenshots/aqe-full-suite")
SHOTS_DIR = ART / "screenshots"
WIZARD_STEPS_DIR = SHOTS_DIR / "wizard_steps"
FLOW_DIR = SHOTS_DIR / "flow"

# Actor email → slug used for flow/<slug>/ directory layout. Mirrors
# ACTOR_SLUGS in run_actor_flow_tests.py.
FLOW_ACTOR_SLUGS = {
    "project-admin@egrm.test":  "project-admin",
    "grm-officer@egrm.test":    "grm-officer",
    "triage-officer@egrm.test": "triage-officer",
    "resolver@egrm.test":       "resolver",
    "field-officer@egrm.test":  "field-officer",
    "grm-dept@egrm.test":       "grm-dept",
}
FLOW_SLUG_TO_EMAIL = {v: k for k, v in FLOW_ACTOR_SLUGS.items()}

# Repeat the classifier from run_ui_screenshots.py here so this module
# can be invoked standalone (e.g. to re-render the HTML from existing
# PNGs without re-running the whole suite).
ERROR_SIGNATURES: list[tuple[str, re.Pattern]] = [
    ("not-permitted", re.compile(
        r"User .+ does not have doctype access via role permission for document .+",
        re.IGNORECASE,
    )),
    ("not-permitted", re.compile(r"Insufficient Permission", re.IGNORECASE)),
    ("not-permitted", re.compile(r"Not permitted\b", re.IGNORECASE)),
    ("not-permitted", re.compile(r"No permission for", re.IGNORECASE)),
    ("server-error", re.compile(r"Internal Server Error", re.IGNORECASE)),
    ("not-found",    re.compile(r"Page not found", re.IGNORECASE)),
    ("not-found",    re.compile(r"DocType .+ does not exist", re.IGNORECASE)),
]
LOGIN_REDIRECT = re.compile(
    r"(Login\s+to\s+|Sign\s*In|"
    r"login_email|Forgot\s+Password|Don.?t\s+have\s+an\s+account)",
    re.IGNORECASE,
)


def classify_text(body: str, *, expects_auth: bool) -> tuple[str, str]:
    body = (body or "").strip()
    if len(body) < 80:
        return "blank", "len<80"
    for verdict, pat in ERROR_SIGNATURES:
        m = pat.search(body)
        if m:
            return verdict, m.group(0)[:160]
    if expects_auth and LOGIN_REDIRECT.search(body):
        m = LOGIN_REDIRECT.search(body)
        return "login-required", m.group(0)[:80]
    return "real-content", ""


# --------------------------------------------------------------------------- helpers

def png_to_data_url(p: Path) -> str:
    """Embed a PNG as a base64 data URL so REPORT.html is portable
    even if the screenshots directory is renamed/moved."""
    if not p.exists():
        return ""
    try:
        b = p.read_bytes()
    except Exception:
        return ""
    return "data:image/png;base64," + base64.b64encode(b).decode("ascii")


def png_relpath(p: Path) -> str:
    """Relative path from REPORT.html → the PNG, for the link tag.
    REPORT.html lives in ART, so files under ART/screenshots/... use
    a `screenshots/...` link target."""
    try:
        return str(p.relative_to(ART))
    except ValueError:
        return str(p)


def text_sidecar(png_path: Path) -> str:
    txt = png_path.with_suffix(".txt")
    if txt.exists():
        try:
            return txt.read_text()
        except Exception:
            return ""
    return ""


def find_screenshot(assertion_name: str) -> Path | None:
    """Map an assertion ID to a screenshot path heuristically."""
    n = assertion_name.lower()
    # UI-SCREENSHOTS sub-suite naming.
    if n.startswith("ui-wizard-step-"):
        # UI-wizard-step-NN  →  screenshots/wizard_steps/wizard_step_NN.png
        m = re.search(r"step-(\d+)", n)
        if m:
            return WIZARD_STEPS_DIR / f"wizard_step_{int(m.group(1)):02d}.png"
    # XD-FIDELITY sub-suite naming: XD-FIDELITY-step-NN (0-based)
    # → wizard_step_{N+1:02d}.png. Steps 12..15 have no capture
    # (unverified).
    if n.startswith("xd-fidelity-step-"):
        m = re.search(r"step-(\d+)", n)
        if m:
            step = int(m.group(1))
            if step <= 11:
                return WIZARD_STEPS_DIR / f"wizard_step_{step + 1:02d}.png"
            return None
    if n.startswith("ui-"):
        # UI-01-login → screenshots/01-login.png
        slug = assertion_name[3:]
        cand = SHOTS_DIR / f"{slug}.png"
        if cand.exists():
            return cand
    # ACTOR-EVIDENCE sub-suite naming: ACTOR-EV-<slug> → actor-<slug>.png
    if n.startswith("actor-ev-"):
        slug = assertion_name[len("ACTOR-EV-"):]
        cand = SHOTS_DIR / f"actor-{slug}.png"
        if cand.exists():
            return cand
    # ACTOR-FLOW sub-suite naming: FLOW-<ACTOR-UPPER>.<action>
    # → flow/<actor-slug>/NN-<action>.png  (where NN is sequence per actor).
    # Some actor slugs are themselves hyphenated (e.g. "triage-officer"),
    # so we resolve by longest-prefix match against FLOW_SLUG_TO_EMAIL.
    if n.startswith("flow-") and "." in assertion_name:
        actor_part, _dot, action = assertion_name[len("FLOW-"):].partition(".")
        actor_slug = actor_part.lower()
        if actor_slug in FLOW_SLUG_TO_EMAIL:
            d = FLOW_DIR / actor_slug
            if d.is_dir():
                # Match the suffix `<NN>-<action>.png` (action may contain
                # underscores; the runner's slugifier preserves them).
                for p in sorted(d.glob(f"*-{action}.png")):
                    return p
    return None


# --------------------------------------------------------------------------- XD references

def load_xd_references() -> dict:
    """Load /Users/victor/egrm/aqe-screenshots/aqe-full-suite/xd_references.json
    so the report can render `XD reference ↗` links per step row."""
    p = ART / "xd_references.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def xd_url_for_assertion(name: str, refs: dict) -> str:
    """Return the verbatim XD URL for an XD-FIDELITY-step-NN assertion."""
    n = name.lower()
    if not n.startswith("xd-fidelity-step-"):
        return ""
    m = re.search(r"step-(\d+)", n)
    if not m:
        return ""
    step = int(m.group(1))
    entry = (refs.get("steps") or {}).get(f"step_{step:02d}") or {}
    return entry.get("xd_url") or ""


def html_escape(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def truncate(s: str, n: int = 600) -> str:
    s = s or ""
    if len(s) <= n:
        return s
    return s[:n] + "  …(truncated)"


# --------------------------------------------------------------------------- styles

CSS = """
:root {
  --pass: #1a7f37;
  --fail: #cf222e;
  --warn: #b35900;
  --muted: #57606a;
  --bg: #ffffff;
  --bg-alt: #f6f8fa;
  --border: #d0d7de;
  --code-bg: #f6f8fa;
}
* { box-sizing: border-box; }
body {
  font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  color: #1f2328;
  background: var(--bg);
  margin: 0;
  padding: 0 24px 80px;
  line-height: 1.45;
}
header.banner {
  position: sticky; top: 0;
  background: linear-gradient(135deg, #1f2328 0%, #2c333b 100%);
  color: #fff;
  margin: 0 -24px 24px;
  padding: 18px 24px;
  z-index: 10;
  box-shadow: 0 1px 3px rgba(0,0,0,.1);
}
header.banner h1 { margin: 0 0 4px; font-size: 18px; }
header.banner .meta { font-size: 12px; opacity: .85; }
header.banner .totals { display: flex; gap: 14px; margin-top: 10px; }
header.banner .totals .pill {
  padding: 4px 10px; border-radius: 12px; font-weight: 600;
}
.pill.pass { background: #d4f5dd; color: #1a7f37; }
.pill.fail { background: #ffd9d3; color: #cf222e; }
.pill.total { background: #e3eef9; color: #0969da; }
.pill.time { background: #f0e6ff; color: #6f42c1; }

.gauge {
  display: inline-block; width: 220px; height: 8px;
  background: #ffd9d3; border-radius: 4px; vertical-align: middle;
  margin-left: 12px; position: relative; overflow: hidden;
}
.gauge .fill { display: block; height: 100%; background: #1a7f37; }

details.suite {
  border: 1px solid var(--border); border-radius: 6px;
  margin: 12px 0; padding: 0; background: var(--bg);
}
details.suite > summary {
  cursor: pointer; padding: 12px 16px; font-weight: 600;
  display: flex; align-items: center; justify-content: space-between;
  list-style: none;
}
details.suite > summary::-webkit-details-marker { display: none; }
details.suite > summary .name { font-size: 15px; }
details.suite[data-status="fail"] > summary { background: #fff5f5; }
details.suite[data-status="pass"] > summary { background: #f4faf6; }
details.suite > .body { padding: 8px 16px 16px; }

table.assertions {
  width: 100%; border-collapse: collapse; margin-top: 8px;
  font-size: 12.5px;
}
table.assertions th,
table.assertions td {
  border-bottom: 1px solid var(--border);
  padding: 6px 8px; text-align: left; vertical-align: top;
}
table.assertions th {
  background: var(--bg-alt); font-size: 11px; text-transform: uppercase;
  letter-spacing: .03em; color: var(--muted);
}
tr.row-pass td.status { color: var(--pass); font-weight: 600; }
tr.row-fail td.status { color: var(--fail); font-weight: 600; }
tr.row-fail { background: #fff5f5; }
.detail { color: var(--muted); font-size: 11.5px; max-width: 480px; word-break: break-word; }
.detail code {
  background: var(--code-bg); border-radius: 3px; padding: 0 4px;
}
.shot {
  display: block; max-width: 320px; max-height: 200px; border: 1px solid var(--border);
  border-radius: 4px; cursor: zoom-in; background: var(--bg-alt);
}
.shot-links {
  font-size: 11.5px; margin: 2px 0 4px;
  display: flex; gap: 6px; flex-wrap: wrap; align-items: center;
}
.shot-links a {
  color: #0969da; text-decoration: none; font-weight: 600;
  padding: 1px 6px; border-radius: 4px; background: var(--bg-alt);
  border: 1px solid var(--border);
}
.shot-links a:hover { background: #e3eef9; }
.shot-links .shot-name code { font-size: 10.5px; color: var(--muted); }
table.assertions.perf td code { font-size: 11px; }
table.assertions.perf td b { color: #1f2328; font-weight: 600; }
.muted { color: var(--muted); }
.over-budget { color: var(--fail); font-weight: 600; }
.shot.bad { border-color: var(--fail); box-shadow: 0 0 0 2px rgba(207,34,46,.2); }
.shot.warn { border-color: var(--warn); }
.verdict-tag {
  display: inline-block; padding: 1px 7px; border-radius: 9px;
  font-size: 11px; font-weight: 600;
}
.verdict-tag.real-content { background: #d4f5dd; color: #1a7f37; }
.verdict-tag.not-permitted { background: #ffd9d3; color: #cf222e; }
.verdict-tag.login-required { background: #fff0c2; color: #b35900; }
.verdict-tag.blank { background: #ffe8d3; color: #b35900; }
.verdict-tag.server-error,
.verdict-tag.not-found { background: #ffd9d3; color: #cf222e; }
.body-text {
  font-family: ui-monospace, SFMono-Regular, "SF Mono", monospace;
  font-size: 11px; color: var(--muted);
  background: var(--code-bg); padding: 6px 8px; border-radius: 4px;
  margin-top: 4px; max-width: 480px; max-height: 110px;
  overflow-y: auto; white-space: pre-wrap; word-break: break-word;
}
.healed {
  border-left: 3px solid var(--pass); padding-left: 14px; margin: 12px 0;
}
.healed code { background: var(--code-bg); padding: 1px 5px; border-radius: 3px; }

.actor-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr));
  gap: 12px; margin-top: 8px;
}
.actor-card {
  border: 1px solid var(--border); border-radius: 6px; padding: 10px;
  background: var(--bg-alt);
}
.actor-card.bad { border-color: var(--fail); background: #fff5f5; }
.actor-card .email { font-weight: 600; font-size: 13px; word-break: break-all; }
.actor-card .role { font-size: 11px; color: var(--muted); margin: 2px 0 6px; }

.flow-strip {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;
}
.flow-thumb {
  width: 96px; height: 64px; object-fit: cover; border: 1px solid var(--border);
  border-radius: 4px; background: var(--bg-alt);
}
.flow-thumb.bad { border-color: var(--fail); }

.flow-chain {
  display: flex; flex-wrap: wrap; gap: 10px;
  align-items: stretch; padding-top: 6px;
}
.flow-step {
  width: 200px; padding: 8px; border: 1px solid var(--border); border-radius: 6px;
  background: var(--bg-alt); display: flex; flex-direction: column; gap: 6px;
}
.flow-step .flow-thumb { width: 100%; height: 110px; }
.flow-step-action { font-size: 12px; font-weight: 600; }
.flow-step-actor  { font-size: 11px; color: var(--muted); word-break: break-all; }
.flow-step-status { font-size: 11px; color: var(--muted); }

.lightbox {
  position: fixed; inset: 0; background: rgba(0,0,0,.85);
  display: none; align-items: center; justify-content: center; z-index: 100;
}
.lightbox.open { display: flex; }
.lightbox img { max-width: 95vw; max-height: 95vh; object-fit: contain; }

footer.foot {
  margin-top: 32px; padding-top: 16px; border-top: 1px solid var(--border);
  font-size: 12px; color: var(--muted);
}
"""


JS = """
document.addEventListener('click', (e) => {
  const t = e.target;
  if (t.tagName === 'IMG' && t.classList.contains('shot')) {
    const lb = document.getElementById('lightbox');
    const big = document.getElementById('lightbox-img');
    big.src = t.dataset.full || t.src;
    lb.classList.add('open');
  } else if (t.id === 'lightbox' || t.id === 'lightbox-img') {
    document.getElementById('lightbox').classList.remove('open');
  }
});
"""


# --------------------------------------------------------------------------- per-suite renderers

def render_assertion_row(suite: str, r: dict, xd_refs: dict | None = None) -> str:
    name = r.get("name", "")
    passed = bool(r.get("passed"))
    detail = r.get("detail") or ""
    klass = "row-pass" if passed else "row-fail"
    status_text = "PASS" if passed else "FAIL"

    extra = ""
    # XD-FIDELITY rows get a clickable reference link to the canonical
    # Adobe XD screen alongside the captured PNG.
    if xd_refs and name.lower().startswith("xd-fidelity-step-"):
        xd_url = xd_url_for_assertion(name, xd_refs)
        if xd_url:
            extra += (
                f"<div class='shot-links'>"
                f"<a href='{html_escape(xd_url)}' target='_blank' rel='noopener' "
                f"title='Open the canonical Adobe XD screen'>🎨 XD reference ↗</a>"
                "</div>"
            )
    png = find_screenshot(name)
    if png and png.exists():
        # Authenticated routes: any 03..08 + every wizard step.
        # Anonymous-OK routes: 01-login, 09-12 public-*.
        is_anon_ok = bool(re.match(
            r"^UI-(01-login|09-public|10-public|11-public|12-public)",
            name,
        ))
        body = text_sidecar(png)
        verdict, sig = classify_text(body, expects_auth=not is_anon_ok)
        cls = "shot"
        if verdict == "not-permitted" or verdict == "server-error" or verdict == "not-found":
            cls += " bad"
        elif verdict == "login-required" and not is_anon_ok:
            cls += " bad"
        elif verdict == "blank":
            cls += " warn"
        data_url = png_to_data_url(png)
        rel = png_relpath(png)
        txt_path = png.with_suffix(".txt")
        txt_rel = png_relpath(txt_path) if txt_path.exists() else ""
        link_bar = (
            f"<div class='shot-links'>"
            f"<a href='{html_escape(rel)}' target='_blank' rel='noopener' "
            f"title='Open full PNG in new tab'>📷 PNG ↗</a>"
            + (
                f" · <a href='{html_escape(txt_rel)}' target='_blank' rel='noopener' "
                f"title='Open captured body text'>📝 text ↗</a>"
                if txt_rel else ""
            )
            + f" · <span class='shot-name'><code>{html_escape(rel)}</code></span>"
            + "</div>"
        )
        extra = (
            link_bar
            + f"<div><a href='{html_escape(rel)}' target='_blank' rel='noopener'>"
            f"<img class='{cls}' src='{html_escape(rel)}' "
            f"data-full='{data_url}' alt='{html_escape(name)}'></a></div>"
            f"<div><span class='verdict-tag {verdict}'>{verdict}</span>"
            + (f" <code>{html_escape(sig)}</code>" if sig else "")
            + "</div>"
        )
        if body and verdict != "real-content":
            extra += (
                f"<div class='body-text'>{html_escape(truncate(body, 600))}</div>"
            )

    return (
        f"<tr class='{klass}'>"
        f"<td class='status'>{status_text}</td>"
        f"<td><code>{html_escape(name)}</code></td>"
        f"<td class='detail'>{html_escape(truncate(detail, 800))}{extra}</td>"
        "</tr>"
    )


def _parse_perf_detail(detail: str) -> dict:
    """Best-effort parse of a PF assertion's detail string into a dict
    with keys like {observed, percentile, n, budget, inputs}.

    Supports two conventions the runner may emit:
    1. JSON tail: `... | json={"p50":78.3,"n":10,"budget":100,"inputs":{...}}`
    2. key=value pairs: `observed=78.3ms percentile=p50 n=10 budget=100ms inputs=(regions=5000,endpoint=/api/...)`

    Falls back to the legacy `(<n>ms ... budget=<n>ms)` shape so old
    JSONs (with the v1 flat detail) still render.
    """
    out: dict = {"raw": detail or ""}
    if not detail:
        return out
    m = re.search(r"\|\s*json=(\{.*\})\s*$", detail)
    if m:
        try:
            j = json.loads(m.group(1))
            if isinstance(j, dict):
                out.update(j)
                return out
        except Exception:
            pass
    for k, v in re.findall(r"(\w+)=([^\s,()]+)", detail):
        if k in {"observed", "p50", "p95", "p99", "budget", "n"}:
            try:
                out[k] = float(v.rstrip("ms").rstrip("s"))
            except ValueError:
                out[k] = v
        elif k == "percentile":
            out[k] = v
    inputs_m = re.search(r"inputs=\(([^)]*)\)", detail)
    if inputs_m:
        out["inputs"] = dict(
            re.findall(r"(\w+)=([^,\s]+)", inputs_m.group(1))
        )
    legacy = re.search(
        r"\((\d+(?:\.\d+)?)ms.*?budget[^=]*=([\d.]+|None)ms", detail
    )
    if legacy and "observed" not in out:
        out["observed"] = float(legacy.group(1))
        bud_raw = legacy.group(2)
        out["budget"] = None if bud_raw == "None" else float(bud_raw)
    return out


def _fmt_inputs(inputs: dict | None) -> str:
    if not inputs:
        return "<span class='muted'>—</span>"
    parts = []
    for k, v in inputs.items():
        parts.append(f"<code>{html_escape(str(k))}=<b>{html_escape(str(v))}</b></code>")
    return " ".join(parts)


def render_perf_table(suite_record: dict) -> str:
    """Render PF-* assertions with inputs and observed-vs-budget detail."""
    rows = []
    for r in suite_record.get("results", []):
        d = _parse_perf_detail(r.get("detail") or "")
        if not any(k in d for k in ("observed", "p50", "p95", "p99", "n")):
            continue
        rows.append((r["name"], d, bool(r["passed"])))
    if not rows:
        return (
            "<h4>Performance budgets</h4>"
            "<p class='muted'>No measurement detail recorded — runner did not "
            "emit observed/budget in the result detail strings.</p>"
        )
    out = [
        "<h4>Performance budgets &mdash; inputs and results</h4>",
        "<table class='assertions perf'>",
        "<tr>"
        "<th style='width:26%'>Assertion</th>"
        "<th style='width:30%'>Inputs</th>"
        "<th style='width:14%'>Observed</th>"
        "<th style='width:10%'>p95</th>"
        "<th style='width:8%'>n</th>"
        "<th style='width:8%'>Budget</th>"
        "<th style='width:4%'>Status</th>"
        "</tr>",
    ]
    for name, d, passed in rows:
        status = "PASS" if passed else "FAIL"
        cls = "row-pass" if passed else "row-fail"
        observed = d.get("observed")
        if observed is None:
            observed = d.get("p50")
        obs_str = f"{observed:.1f} ms" if isinstance(observed, (int, float)) else "—"
        p95 = d.get("p95")
        p95_str = f"{p95:.1f} ms" if isinstance(p95, (int, float)) else "—"
        n_val = d.get("n")
        n_str = str(int(n_val)) if isinstance(n_val, (int, float)) else "—"
        bud = d.get("budget")
        bud_str = f"{bud:.0f} ms" if isinstance(bud, (int, float)) else "—"
        over_budget = (
            isinstance(bud, (int, float))
            and isinstance(observed, (int, float))
            and observed >= bud
        )
        obs_html = (
            f"<span class='over-budget'>{obs_str}</span>" if over_budget else obs_str
        )
        out.append(
            f"<tr class='{cls}'>"
            f"<td><code>{html_escape(name)}</code></td>"
            f"<td>{_fmt_inputs(d.get('inputs'))}</td>"
            f"<td>{obs_html}</td>"
            f"<td>{p95_str}</td>"
            f"<td>{n_str}</td>"
            f"<td>{bud_str}</td>"
            f"<td class='status'>{status}</td>"
            "</tr>"
        )
    out.append("</table>")
    return "\n".join(out)


def render_suite_section(s: dict, xd_refs: dict | None = None) -> str:
    name = s.get("suite") or ""
    passed = s.get("passed") or 0
    failed = s.get("failed") or 0
    total = s.get("total") or 0
    elapsed = s.get("elapsed_s") or 0
    status = "pass" if failed == 0 and (s.get("exit_code") in (None, 0)) else "fail"

    rows = "\n".join(
        render_assertion_row(name, r, xd_refs) for r in s.get("results", [])
    )

    perf = render_perf_table(s) if name == "PERFORMANCE" else ""

    return f"""
<details class="suite" data-status="{status}" {'open' if status=='fail' else ''}>
  <summary>
    <span class="name">{html_escape(name)}</span>
    <span>
      <span class="pill {'pass' if failed==0 else 'fail'}">{passed} / {total}</span>
      <span class="pill time">{elapsed:.1f}s</span>
    </span>
  </summary>
  <div class="body">
    {perf}
    <table class="assertions">
      <tr><th style='width:6%'>Status</th><th style='width:34%'>Assertion</th><th>Detail</th></tr>
      {rows}
    </table>
  </div>
</details>
"""


# --------------------------------------------------------------------------- per-actor evidence

ACTORS = [
    # Per-actor evidence cards. The first entry of `sample_pngs` is
    # always the canonical capture produced by run_actor_evidence.py
    # (`actor-<slug>.png` — fresh per-actor session, duty-relevant
    # route). For project-admin we additionally surface the wider
    # UI-SCREENSHOTS captures because the platform admin's duty spans
    # more surfaces than any single shot can prove.
    ("project-admin@egrm.test", "GRM Platform Administrator + GRM Supervise",
     [SHOTS_DIR / "actor-project-admin.png",
      SHOTS_DIR / "02-admin-desk.png",
      SHOTS_DIR / "03-grm-project-list.png",
      SHOTS_DIR / "07-grm-users.png",
      SHOTS_DIR / "08-grm-project-wizard.png"]),
    ("field-officer@egrm.test", "GRM Intake (intake-only)",
     [SHOTS_DIR / "actor-field-officer.png"]),
    ("triage-officer@egrm.test", "GRM Review + Assignment",
     [SHOTS_DIR / "actor-triage-officer.png"]),
    ("resolver@egrm.test", "GRM Investigate & Resolve + Feedback",
     [SHOTS_DIR / "actor-resolver.png"]),
    ("grm-officer@egrm.test", "GRM Intake + Investigate & Resolve + Feedback (mobile)",
     [SHOTS_DIR / "actor-grm-officer.png"]),
    ("grm-dept@egrm.test", "GRM full inner-workflow (district)",
     [SHOTS_DIR / "actor-grm-dept.png"]),
]


# --------------------------------------------------------------------------- ACTOR-FLOW renderer
#
# The ACTOR-FLOW sub-suite stages 3 lifecycle chains (citizen-origin,
# mobile-origin, desk-origin). Each FLOW-<ACTOR>.<action> assertion has a
# matching screenshots/flow/<slug>/NN-<action>.png. We render two extra
# views below the regular suite table:
#   - per-actor flow grid: every PNG that actor produced this run
#   - per-chain story strip: chronological actions for chain-1/2/3,
#     each row = (assertion, status, screenshot thumb) so reviewers can
#     "watch" the issue walk to terminal state.
def _flow_assertions(report: dict) -> list[dict]:
    for s in report.get("suites") or []:
        if (s.get("suite") or "").upper() == "ACTOR-FLOW":
            return list(s.get("results") or [])
    return []


def _parse_flow_detail(detail: str) -> dict:
    """Pull `actor=`, `action=`, `issue=`, `status=`, `screenshot=`,
    `http=` tokens out of a FLOW-* assertion's detail line."""
    out: dict = {}
    if not detail:
        return out
    # screenshot path token (no spaces in our slugifier).
    m = re.search(r"screenshot=([^\s]+)", detail)
    if m:
        out["screenshot"] = m.group(1)
    for key in ("actor", "action", "issue", "status", "http"):
        m = re.search(rf"\b{key}=([^\s]+)", detail)
        if m:
            out[key] = m.group(1)
    return out


def render_flow_actor_grid(report: dict) -> str:
    """One card per actor with thumbnails of every action they performed."""
    flow = _flow_assertions(report)
    if not flow:
        return ""
    by_actor: dict[str, list[dict]] = {}
    for r in flow:
        name = r.get("name", "")
        if not name.startswith("FLOW-") or "." not in name:
            continue
        # Skip CHAIN-N.terminal_status / CHAIN-N.seed_* / FLOW-0.*
        actor_part = name[len("FLOW-"):].split(".", 1)[0].lower()
        if actor_part not in FLOW_SLUG_TO_EMAIL:
            continue
        info = _parse_flow_detail(r.get("detail", ""))
        info["name"] = name
        info["passed"] = r.get("passed", False)
        by_actor.setdefault(actor_part, []).append(info)
    if not by_actor:
        return ""
    cards = []
    for slug, rows in by_actor.items():
        email = FLOW_SLUG_TO_EMAIL[slug]
        thumbs = []
        for info in rows:
            shot = info.get("screenshot")
            if not shot:
                continue
            png = ART / shot
            if not png.exists():
                continue
            rel = png_relpath(png)
            cls = "shot" if info.get("passed") else "shot bad"
            thumbs.append(
                f"<a href='{html_escape(rel)}' target='_blank' "
                f"title='{html_escape(info.get('action',''))} — "
                f"http={html_escape(info.get('http','?'))} "
                f"status={html_escape(info.get('status','?'))}'>"
                f"<img class='{cls} flow-thumb' src='{html_escape(rel)}' "
                f"alt='{html_escape(info['name'])}'></a>"
            )
        action_count = len(rows)
        passed_count = sum(1 for i in rows if i.get("passed"))
        meta = (f"{passed_count}/{action_count} actions passed")
        cards.append(f"""
<div class="actor-card">
  <div class="email">{html_escape(email)}</div>
  <div class="role">{html_escape(meta)}</div>
  <div class="flow-strip">{''.join(thumbs) or '<em>(no captures)</em>'}</div>
</div>
""")
    return f"<div class='actor-grid'>{''.join(cards)}</div>"


def render_flow_chain_strips(report: dict) -> str:
    """Three story strips — one per chain (CHAIN-1/2/3) — chronological
    sequence of every action that touched the chain's issue."""
    flow = _flow_assertions(report)
    if not flow:
        return ""
    # Discover chain → issue_name from CHAIN-N.seed_* (or any CHAIN-N row).
    chain_issue: dict[str, str] = {}
    chain_terminal: dict[str, dict] = {}
    for r in flow:
        name = r.get("name", "")
        m = re.match(r"FLOW-CHAIN-(\d+)\.(\w+)", name)
        if not m:
            continue
        chain = m.group(1)
        info = _parse_flow_detail(r.get("detail", ""))
        if info.get("issue") and chain not in chain_issue:
            chain_issue[chain] = info["issue"]
        if m.group(2) == "terminal_status":
            chain_terminal[chain] = {
                "passed": r.get("passed", False),
                "detail": r.get("detail", ""),
            }
    if not chain_issue:
        return ""
    # Group action rows by chain via issue=... match.
    chains: dict[str, list[dict]] = {c: [] for c in chain_issue}
    # Preserve chronological order — the runner records actions in chain order.
    for r in flow:
        name = r.get("name", "")
        if not name.startswith("FLOW-") or name.startswith("FLOW-CHAIN-"):
            continue
        if name.startswith("FLOW-0."):
            continue
        info = _parse_flow_detail(r.get("detail", ""))
        info["name"] = name
        info["passed"] = r.get("passed", False)
        info["detail"] = r.get("detail", "")
        issue = info.get("issue")
        if not issue:
            continue
        for chain, iname in chain_issue.items():
            if iname == issue:
                chains[chain].append(info)
                break
    if not any(chains.values()):
        return ""
    strips = []
    chain_titles = {
        "1": "Chain 1 — Citizen origin → resolver → close",
        "2": "Chain 2 — Mobile origin → reopen → re-resolve",
        "3": "Chain 3 — Desk origin → escalate → resolve",
    }
    for chain in sorted(chains):
        rows = chains[chain]
        if not rows:
            continue
        terminal = chain_terminal.get(chain, {})
        terminal_cls = "pass" if terminal.get("passed") else "fail"
        terminal_text = "terminal status: PASS" if terminal.get("passed") else "terminal status: FAIL"
        steps = []
        for info in rows:
            shot = info.get("screenshot")
            png = ART / shot if shot else None
            thumb = ""
            if png and png.exists():
                rel = png_relpath(png)
                cls = "shot" if info.get("passed") else "shot bad"
                thumb = (
                    f"<a href='{html_escape(rel)}' target='_blank'>"
                    f"<img class='{cls} flow-thumb' src='{html_escape(rel)}'></a>"
                )
            actor = info.get("actor", "?")
            action = info.get("action", info["name"].split(".", 1)[-1])
            status = info.get("status", "?")
            badge = "✓" if info.get("passed") else "✗"
            badge_cls = "pass" if info.get("passed") else "fail"
            steps.append(f"""
<div class="flow-step">
  {thumb}
  <div class="flow-step-meta">
    <div class="flow-step-action"><span class="pill {badge_cls}">{badge}</span> <code>{html_escape(action)}</code></div>
    <div class="flow-step-actor">{html_escape(actor)}</div>
    <div class="flow-step-status">status: <code>{html_escape(status)}</code></div>
  </div>
</div>
""")
        title = chain_titles.get(chain, f"Chain {chain}")
        strips.append(f"""
<details class="suite" open>
  <summary>
    <span class="pill {terminal_cls}">{html_escape(terminal_text)}</span>
    {html_escape(title)}
    <span class="meta">issue: <code>{html_escape(chain_issue[chain])}</code></span>
  </summary>
  <div class="body">
    <div class="flow-chain">{''.join(steps)}</div>
  </div>
</details>
""")
    return "".join(strips)


def render_actor_grid() -> str:
    cards = []
    for email, role, sample_pngs in ACTORS:
        # Look for any captured PNG that proves real-content for this actor.
        pngs = [p for p in sample_pngs if p.exists()]
        verdicts = []
        for p in pngs:
            body = text_sidecar(p)
            verdict, _sig = classify_text(body, expects_auth=True)
            verdicts.append((p, verdict))
        any_real = any(v == "real-content" for _p, v in verdicts)
        cls = "actor-card" if any_real or not pngs else "actor-card bad"
        thumb = ""
        if verdicts:
            for p, v in verdicts:
                if v == "real-content":
                    rel = png_relpath(p)
                    thumb = (
                        f"<a href='{html_escape(rel)}' target='_blank'>"
                        f"<img class='shot' src='{html_escape(rel)}' "
                        f"alt='{html_escape(email)} evidence'></a>"
                        f"<div><code>{html_escape(rel)}</code></div>"
                    )
                    break
        if not thumb and verdicts:
            # fall back to the first one with its bad verdict so the
            # report shows what the actor saw instead.
            p, v = verdicts[0]
            rel = png_relpath(p)
            thumb = (
                f"<img class='shot bad' src='{html_escape(rel)}' "
                f"alt='{html_escape(email)} {v}'>"
                f"<div><span class='verdict-tag {v}'>{v}</span></div>"
            )
        cards.append(f"""
<div class="{cls}">
  <div class="email">{html_escape(email)}</div>
  <div class="role">{html_escape(role)}</div>
  {thumb or '<div class="role">(no captured evidence yet)</div>'}
</div>
""")
    return f"<div class='actor-grid'>{''.join(cards)}</div>"


# --------------------------------------------------------------------------- main

def render_html(report: dict, healed: list[dict] | None = None) -> str:
    totals = report.get("totals") or {}
    passed = totals.get("passed", 0)
    failed = totals.get("failed", 0)
    total = totals.get("total", 0)
    pct = (100 * passed / total) if total else 0
    elapsed = report.get("elapsed_s", 0)
    site = report.get("site", "")
    gen_at = report.get("generated_at") or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S")

    xd_refs = load_xd_references()
    suite_html = "\n".join(
        render_suite_section(s, xd_refs) for s in report.get("suites") or []
    )

    healed_html = ""
    if healed:
        items = []
        for h in healed:
            items.append(
                f"<div class='healed'>"
                f"<strong>{html_escape(h['assertion'])}</strong> — "
                f"<em>{html_escape(h.get('root_cause',''))}</em><br>"
                f"<code>{html_escape(h.get('app_file',''))}</code>"
                + (f"<br>{html_escape(h.get('fix_summary',''))}"
                   if h.get('fix_summary') else "")
                + "</div>"
            )
        healed_html = (
            "<h2>Healed in this run</h2>" + "\n".join(items)
        )

    actor_section = render_actor_grid()
    flow_actor_section = render_flow_actor_grid(report)
    flow_chain_section = render_flow_chain_strips(report)

    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<title>AQE Full Suite — {site}</title>
<style>{CSS}</style>
</head>
<body>
<header class="banner">
  <h1>AQE Full Suite — {html_escape(site)}</h1>
  <div class="meta">Generated {html_escape(gen_at)} &middot; wall time {elapsed:.1f}s</div>
  <div class="totals">
    <span class="pill pass">{passed} passed</span>
    <span class="pill fail">{failed} failed</span>
    <span class="pill total">{total} total</span>
    <span class="pill time">{elapsed:.1f}s</span>
    <span style="display:inline-flex; align-items:center;">
      <span class="gauge"><span class="fill" style="width:{pct:.1f}%"></span></span>
      <span style="margin-left:8px; font-weight:600;">{pct:.1f}%</span>
    </span>
  </div>
</header>

<h2>Per-actor evidence</h2>
<p style="color:var(--muted)">Each canonical actor's most informative
captured screen. Cards turn red when the only evidence we have for the
actor is a permission dialog or login redirect.</p>
{actor_section}

<h2>Per-actor lifecycle actions</h2>
<p style="color:var(--muted)">For every action a canonical actor's
duty(ies) permit, a per-action PNG is captured under a fresh per-actor
session. Each thumbnail's title carries the assertion's
<code>http=</code> + status code. Click any thumb to open the full PNG.</p>
{flow_actor_section}

<h2>Issue lifecycle chains</h2>
<p style="color:var(--muted)">Three chains stage one issue each through
every state transition the canonical workflow exposes — citizen-origin
(public submit → close), mobile-origin (push → reopen → re-resolve),
and desk-origin (officer-create → escalate → grm-dept resolves). The
per-chain pill shows whether the issue actually reached its terminal
status server-side.</p>
{flow_chain_section}

<h2>Suites</h2>
{suite_html}

{healed_html}

<footer class='foot'>
Generated by <code>make_html_report.py</code> from <code>REPORT.json</code>
plus inline content classification of each captured PNG. Click any
screenshot for a fullscreen view.
</footer>

<div id="lightbox" class="lightbox"><img id="lightbox-img" src=""></div>
<script>{JS}</script>
</body>
</html>"""


def load_report() -> dict:
    p = ART / "REPORT.json"
    if not p.exists():
        sys.exit(f"REPORT.json not found at {p}; run run_full_suite.py first")
    return json.loads(p.read_text())


def load_healed() -> list[dict]:
    """Optional companion file the orchestrator drops alongside REPORT.json
    so the report can show a 'healed-in-this-run' section."""
    p = ART / "HEALED_THIS_RUN.json"
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def main() -> int:
    report = load_report()
    healed = load_healed()
    out = ART / "REPORT.html"
    out.write_text(render_html(report, healed))
    n_pngs = len(list(SHOTS_DIR.rglob("*.png")))
    print(f"[make_html_report] wrote {out} ({n_pngs} PNGs embedded by reference)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
