"""SUITE: UI screenshots — MacBook 13" full-screen viewport (1440×900).

V2: every PNG is also classified by *rendered text*. A capture that
matches one of the well-known error-dialog signatures fails the
assertion even if the PNG itself is on disk and >1KB.

Captures the eGRM web UI at the canonical MacBook 13" full-screen CSS
viewport size (1440×900 — the default logical resolution for the
13" Air/Pro since the M1 generation in browser full-screen mode).

Screenshots are saved under
    /Users/victor/egrm/aqe-screenshots/aqe-full-suite/screenshots/

Layout: NN-page-name.png  (NN is the capture order, zero-padded).
For each PNG we also write `<name>.txt` containing the body inner_text
so the HTML report can show the smoking-gun text alongside the image.

Targets:
  - Login screen (anonymous)
  - Admin desk landing (post-login)
  - Project wizard (every step 1..TOTAL_STEPS via aqe_force_step=N
    against the seeded RW-WB project)
  - GRM Project list / detail
  - GRM Issue list
  - Custom Users-by-Project page (canonical name `grm-users`)
  - Public-side: dashboard, submit page, track page, reports page

Each capture runs at FULL_PAGE=True so long pages render top to bottom
within the viewport-width frame.

Prereq: Frappe site running on http://egrm.local:8000.
Optional: ONBOARDING suite (so the wizard / project list are populated).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from _common import (
    ACTOR_PROJECT_ADMIN, ART, SITE, SuiteRun, run, summary,
)

# MacBook 13" Retina (Air/Pro 2020+) — full-screen browser CSS viewport.
VIEWPORT = {"width": 1440, "height": 900}

# The wizard ships TOTAL_STEPS=12 steps (see grm_project_wizard.js).
WIZARD_TOTAL_STEPS = 12

# Project to drive the wizard step shots against. ONBOARDING seeds RW-WB
# fully, so it has a current_setup_step we can land on for any N.
WIZARD_PROJECT_CODE = "RW-WB"

SHOTS_DIR = ART / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


# Each entry: (slug, path, requires_login, full_page, wait_selector_or_None)
PAGES = [
    ("01-login",                   "/login",                            False, False, "input[name='login_email'], input#login_email"),
    # NOTE: project-admin@egrm.test lands on `/app/platform` per
    # `role_home_page['GRM Platform Administrator']`. The bare `/app`
    # URL renders an empty desk for non-System-Manager users (no
    # auto-redirect after the initial login), so we explicitly target
    # the canonical platform-admin landing page.
    ("02-admin-desk",              "/app/platform",                     True,  False, ".layout-main-section, .desk-page"),
    ("03-grm-project-list",        "/app/grm-project",                  True,  True,  ".layout-main-section, .desk-page"),
    ("04-grm-issue-list",          "/app/grm-issue",                    True,  True,  ".layout-main-section, .desk-page"),
    ("05-grm-administrative-region","/app/grm-administrative-region",   True,  True,  ".layout-main-section, .desk-page"),
    ("06-grm-issue-status-list",   "/app/grm-issue-status",             True,  True,  ".layout-main-section, .desk-page"),
    # Canonical custom-page name is `grm-users` (Page DocType record name).
    ("07-grm-users",               "/app/grm-users",                    True,  False, ".layout-main-section, .grm-users-page"),
    ("08-grm-project-wizard",      "/app/grm-project-wizard",           True,  True,  ".grm-wizard, .layout-main-section"),
    ("09-public-dashboard",        "/grievance-dashboard",              False, True,  None),
    ("10-public-submit",           "/grievance",                        False, True,  None),
    ("11-public-track",            "/track-complaint",                  False, True,  None),
    ("12-public-reports",          "/grievance-reports",                False, True,  None),
]


# ---------------------------------------------------------------------- CONTENT CLASSIFIER
#
# Patterns flagged as a *failed* capture even when the PNG is on disk.
# The leftmost group is the verdict slug recorded into the .txt sidecar
# and surfaced in the HTML report.
#
# Order matters: more specific signatures first.
ERROR_SIGNATURES: list[tuple[str, re.Pattern]] = [
    # The exact dialog the user rejected v1 over.
    ("not-permitted", re.compile(
        r"User .+ does not have doctype access via role permission for document .+",
        re.IGNORECASE,
    )),
    ("not-permitted", re.compile(r"Insufficient Permission", re.IGNORECASE)),
    ("not-permitted", re.compile(r"Not permitted\b", re.IGNORECASE)),
    ("not-permitted", re.compile(r"No permission for", re.IGNORECASE)),
    # 404 / 500 surfaces.
    ("server-error", re.compile(r"Internal Server Error", re.IGNORECASE)),
    ("not-found",    re.compile(r"Page not found", re.IGNORECASE)),
    ("not-found",    re.compile(r"DocType .+ does not exist", re.IGNORECASE)),
]

# Login-redirect signature — only flagged when the path was an
# authenticated route and the rendered page is the Frappe login form.
LOGIN_REDIRECT = re.compile(
    r"(Login\s+to\s+|Sign\s*In|"
    r"login_email|Forgot\s+Password|Don.?t\s+have\s+an\s+account)",
    re.IGNORECASE,
)


def classify_content(text: str, *, expects_auth: bool, slug: str) -> tuple[str, str]:
    """Return (verdict, matched_signature_or_empty_string).

    verdict is one of: real-content, not-permitted, login-required,
    blank, server-error, not-found.
    """
    body = (text or "").strip()
    if len(body) < 80:
        return "blank", "len<80"
    for verdict, pat in ERROR_SIGNATURES:
        m = pat.search(body)
        if m:
            return verdict, m.group(0)[:120]
    if expects_auth and LOGIN_REDIRECT.search(body):
        # Don't let the login screen masquerade as a logged-in page.
        m = LOGIN_REDIRECT.search(body)
        return "login-required", m.group(0)[:80]
    return "real-content", ""


def body_text(page) -> str:
    """Return the rendered body inner_text. Best-effort, never raises."""
    try:
        return page.locator("body").inner_text(timeout=4000)
    except Exception:
        try:
            return page.content()
        except Exception:
            return ""


def perceptual_hash(png_path: Path) -> str:
    """Cheap content fingerprint — just sha1 of bytes. Good enough to
    detect "every step rendered identically" without pulling in PIL."""
    try:
        return hashlib.sha1(png_path.read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def main() -> int:
    suite = SuiteRun("UI-SCREENSHOTS")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        suite.ok("UI-0.playwright_available", False,
                 f"install with: pip install playwright && playwright install chromium ({e})")
        return summary(suite)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport=VIEWPORT,
            device_scale_factor=2,         # Retina
            ignore_https_errors=True,
        )
        page = context.new_page()

        # ---- log in once as platform admin ---------------------------
        email, pwd = ACTOR_PROJECT_ADMIN
        try:
            page.goto(f"{SITE}/login", wait_until="networkidle", timeout=30_000)
            # Frappe login form: #login_email, #login_password
            page.locator("#login_email").fill(email)
            page.locator("#login_password").fill(pwd)
            page.locator("button.btn-login, .btn.btn-primary").first.click()
            page.wait_for_url("**/app**", timeout=20_000)
            suite.ok("UI-0.admin_login", True, "via /login UI")
        except Exception as e:
            suite.ok("UI-0.admin_login", False, f"{type(e).__name__}: {e}")
            # Continue with anonymous shots only.

        # ---- iterate pages -----------------------------------------------
        for slug, path, needs_login, full_page, wait_sel in PAGES:
            out = SHOTS_DIR / f"{slug}.png"
            txt_out = SHOTS_DIR / f"{slug}.txt"
            url = f"{SITE}{path}"

            try:
                # For anonymous shots we want a fresh, logged-out context.
                if not needs_login:
                    anon = browser.new_context(
                        viewport=VIEWPORT,
                        device_scale_factor=2,
                        ignore_https_errors=True,
                    )
                    apage = anon.new_page()
                    apage.goto(url, wait_until="networkidle", timeout=30_000)
                    if wait_sel:
                        try:
                            apage.wait_for_selector(wait_sel, timeout=5_000)
                        except Exception:
                            pass
                    # Wait for SPA hydration / public template render
                    # (grm-portal React app routes /grievance-* and
                    # /track-complaint via client-side routing — first
                    # paint after `networkidle` is still empty).
                    try:
                        apage.wait_for_function(
                            "() => document.body && "
                            "document.body.innerText.replace(/\\s+/g,' ').trim().length > 200",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    apage.screenshot(path=str(out), full_page=full_page)
                    text = body_text(apage)
                    apage.close()
                    anon.close()
                else:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    if wait_sel:
                        try:
                            page.wait_for_selector(wait_sel, timeout=5_000)
                        except Exception:
                            pass
                    # Wait for the SPA / desk to actually render meaningful
                    # body content before screenshotting. A bare workspace
                    # with only a header bar measures <80 chars of inner_text
                    # and gets classified as `blank`. We poll for >=200
                    # chars, which is enough to confirm content rendered.
                    try:
                        page.wait_for_function(
                            "() => document.body && "
                            "document.body.innerText.replace(/\\s+/g,' ').trim().length > 200",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    page.screenshot(path=str(out), full_page=full_page)
                    text = body_text(page)

                txt_out.write_text(text or "")
                size = out.stat().st_size if out.exists() else 0
                verdict, sig = classify_content(
                    text, expects_auth=needs_login, slug=slug,
                )
                # File-existence sub-assertion (kept for forensics).
                file_ok = out.exists() and size > 1024
                # Verdict sub-assertion: must be real-content for an
                # authenticated route. Anonymous public routes may
                # legitimately render the public site (real-content) or
                # a login banner — but they MUST NOT render a permission
                # dialog or 5xx error.
                if needs_login:
                    verdict_ok = (verdict == "real-content")
                else:
                    verdict_ok = verdict in ("real-content", "login-required")
                detail = (
                    f"{out.name} ({size}B, sha1={perceptual_hash(out)}) "
                    f"viewport={VIEWPORT['width']}x{VIEWPORT['height']} "
                    f"verdict={verdict}"
                    + (f" sig=<{sig}>" if sig else "")
                )
                suite.ok(f"UI-{slug}", file_ok and verdict_ok, detail)
            except Exception as e:
                suite.ok(f"UI-{slug}", False,
                         f"{path}: {type(e).__name__}: {str(e)[:200]}")

        # ---- per-wizard-step BODY captures for XD fidelity ----------------
        # ONBOARDING runs BEFORE this suite, so the wizard URL serves
        # populated state. We capture ONE PNG per wizard step using the
        # `aqe_force_step` URL handler that grm_project_wizard.js
        # honours (test-only — see comment in load_project()).
        BODY_SELECTORS = [
            ".grm-project-wizard .wizard-body",
            ".grm-project-wizard",
            ".grm-wizard",
            ".layout-main-section .page-body",
            ".layout-main-section",
        ]
        wizard_step_dir = SHOTS_DIR / "wizard_steps"
        wizard_step_dir.mkdir(exist_ok=True)
        seen_hashes: dict[str, str] = {}
        try:
            for step in range(1, WIZARD_TOTAL_STEPS + 1):
                step_url = (
                    f"{SITE}/app/grm-project-wizard"
                    f"?project={WIZARD_PROJECT_CODE}"
                    f"&aqe_force_step={step}"
                )
                out = wizard_step_dir / f"wizard_step_{step:02d}.png"
                txt_out = wizard_step_dir / f"wizard_step_{step:02d}.txt"
                try:
                    page.goto(step_url, wait_until="networkidle",
                              timeout=20_000)
                    # Wait for the wizard shell to mount and the title to
                    # update — not infallible, but better than fixed sleeps.
                    try:
                        page.wait_for_selector(".grm-wizard", timeout=8000)
                        page.wait_for_function(
                            "() => {"
                            "  const t = document.querySelector('.grm-wizard-title');"
                            f"  return t && t.textContent.startsWith('{step}.');"
                            "}",
                            timeout=8000,
                        )
                    except Exception:
                        pass
                    body_loc = None
                    for sel in BODY_SELECTORS:
                        loc = page.locator(sel).first
                        try:
                            if loc.count() > 0 and loc.is_visible():
                                body_loc = loc
                                break
                        except Exception:
                            continue
                    if body_loc is not None:
                        body_loc.screenshot(path=str(out))
                        captured = "body-only"
                    else:
                        page.screenshot(path=str(out), full_page=True)
                        captured = "full-page-fallback"
                    text = body_text(page)
                    txt_out.write_text(text or "")
                    verdict, sig = classify_content(
                        text, expects_auth=True, slug=f"wizard-step-{step:02d}",
                    )
                    h = perceptual_hash(out)
                    seen_hashes[f"step_{step:02d}"] = h
                    file_ok = out.exists() and out.stat().st_size > 1024
                    verdict_ok = (verdict == "real-content")
                    detail = (
                        f"{out.name} ({out.stat().st_size}B, sha1={h}, "
                        f"{captured}) verdict={verdict}"
                        + (f" sig=<{sig}>" if sig else "")
                    )
                    suite.ok(
                        f"UI-wizard-step-{step:02d}",
                        file_ok and verdict_ok, detail,
                    )
                except Exception as e:
                    suite.ok(
                        f"UI-wizard-step-{step:02d}",
                        False, f"{type(e).__name__}: {e}",
                    )
            # Cross-step uniqueness check — every step must render a
            # distinct screen body (the v1 failure mode was 16
            # byte-identical PNGs of the "Not permitted" dialog).
            unique_hashes = set(seen_hashes.values()) - {""}
            suite.ok(
                "UI-wizard-step-distinct-renders",
                len(unique_hashes) >= max(1, WIZARD_TOTAL_STEPS - 2),
                f"{len(unique_hashes)} distinct hashes across "
                f"{WIZARD_TOTAL_STEPS} steps "
                f"({len(seen_hashes) - len(unique_hashes)} collisions)",
            )
        except Exception as e:
            suite.ok("UI-wizard-step-loop",
                     False, f"{type(e).__name__}: {e}")

        browser.close()

    # ---- emit XD_FIDELITY_REPORT.md (manual side-by-side) ---------------
    refs_path = ART / "design_refs.json"
    if refs_path.exists():
        try:
            refs = json.loads(refs_path.read_text())
        except Exception:
            refs = {}
        screens: dict = refs.get("screens") or {}
        notes: dict = refs.get("notes") or {}
        report = ART / "XD_FIDELITY_REPORT.md"
        lines = [
            "# XD Fidelity Report",
            "",
            "Open each XD screen URL alongside the matching captured PNG ",
            "and check **wizard body only** — layout, copy, spacing, palette. ",
            "Do NOT flag Frappe sidebar/header differences: those are stock ",
            "Frappe chrome and out of scope of the XD design.",
            "",
            f"Branding root: {refs.get('xd_project_root', '(unknown)')}",
            "",
            "| Step | XD Screen | Captured Body PNG | Notes |",
            "|-----:|-----------|-------------------|-------|",
        ]
        wizard_step_dir = SHOTS_DIR / "wizard_steps"
        for step in sorted(int(k) for k in screens.keys()):
            url = screens[str(step)] if str(step) in screens else screens.get(step, "")
            png = wizard_step_dir / f"wizard_step_{step:02d}.png"
            png_link = (str(png) if png.exists()
                        else "(not captured — see UI-SCREENSHOTS log)")
            note_list = notes.get(str(step)) or notes.get(step) or []
            note_md = "<br>".join(note_list) if isinstance(
                note_list, list) else str(note_list)
            lines.append(f"| {step} | {url} | {png_link} | {note_md} |")
        report.write_text("\n".join(lines))
        suite.ok("UI-xd_fidelity_report_written",
                 report.exists(), f"-> {report}")
    else:
        suite.ok("UI-xd_fidelity_report_written", False,
                 "design_refs.json missing — ONBOARDING must run first")

    print(f"\n[UI-SCREENSHOTS] saved {len(list(SHOTS_DIR.glob('*.png')))} images "
          f"to {SHOTS_DIR}")
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
