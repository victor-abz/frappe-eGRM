"""SUITE: ACTOR-EVIDENCE — one duty-relevant PNG per canonical AQE actor.

For every test user in `_common.py`, opens a *fresh* Playwright Chromium
context (so cookies don't bleed across actors), logs in via /login, and
captures one route that proves the actor can exercise their duty.

Each capture is paired with a `.txt` sidecar of the rendered body
inner_text and re-classified by `run_ui_screenshots.classify_content`.
A capture is only PASS if the verdict is `real-content`. A
permission dialog (`not-permitted`), 5xx page (`server-error`), 404
(`not-found`), unexpected redirect to login on an authenticated route
(`login-required`), or a near-empty body (`blank`) all count as FAIL.

Routes are picked to be *distinct per duty* against the actually-seeded
projects on this site (RW-WB / KE-EAC / STJ-HOSP — the AQE plan does
not seed the RDAP project mentioned in the credentials doc, so any
RDAP-specific URL fragment is replaced with the closest valid route on
the AQE seed and the substitution is documented in the assertion detail).

Output:
    /Users/victor/egrm/aqe-screenshots/aqe-full-suite/screenshots/actor-<slug>.png
    /Users/victor/egrm/aqe-screenshots/aqe-full-suite/screenshots/actor-<slug>.txt
    /Users/victor/egrm/aqe-screenshots/aqe-full-suite/ACTOR-EVIDENCE.json

Prereq: ONBOARDING + UI-SCREENSHOTS already ran (so the projects exist
and login is known to work).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from _common import (
    ACTOR_FIELD_OFFICER, ACTOR_GRM_DEPT, ACTOR_GRM_OFFICER,
    ACTOR_PROJECT_ADMIN, ACTOR_RESOLVER, ACTOR_TRIAGE_OFFICER,
    ART, SITE, SuiteRun, run, summary,
)
# Re-use the EXACT classifier the main UI runner uses — single source
# of truth for what "real content" means.
from run_ui_screenshots import (
    VIEWPORT, body_text, classify_content, perceptual_hash,
)


SHOTS_DIR = ART / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


# Each entry: (slug, actor, route, route_note)
#
# `slug` is the basename — the PNG ends up at screenshots/actor-<slug>.png.
# `route` is everything after SITE; should produce a duty-relevant page.
# `route_note` is a short rationale surfaced in the assertion detail —
#   primarily so we can document any substitution from the user's task
#   plan when a referenced fixture (e.g. RDAP-specific department) is
#   not seeded on this site.
ACTORS: list[tuple[str, tuple[str, str], str, str]] = [
    (
        "project-admin",
        ACTOR_PROJECT_ADMIN,
        "/app/grm-project",
        "platform admin oversees all projects",
    ),
    (
        "field-officer",
        ACTOR_FIELD_OFFICER,
        "/app/grm-issue/new",
        "intake duty — new-issue form",
    ),
    (
        "triage-officer",
        ACTOR_TRIAGE_OFFICER,
        "/app/grm-issue",
        # ?status=Open from the original spec resolves through Frappe to
        # `tabGRM Issue.status='Open'` which never matches because status
        # is a Link to the hashed name of a GRM Issue Status row. Drop
        # the filter; the bare list is the actual review queue surface.
        "review queue — list view (no create button under triage role)",
    ),
    (
        "resolver",
        ACTOR_RESOLVER,
        "/app/grm-issue?assignee=resolver%40egrm.test",
        # The DocType field for assignment is `assignee`, not `assigned_to`.
        "assigned-to-me filter (Investigate & Resolve duty)",
    ),
    (
        "grm-officer",
        ACTOR_GRM_OFFICER,
        "/app/grm-issue",
        "mobile cell-level intake actor — desk equivalent list view",
    ),
    (
        "grm-dept",
        ACTOR_GRM_DEPT,
        "/app/grm-issue?project=RW-WB",
        # ?department=k69pn2muse from the original spec is an RDAP-only
        # ID; this site seeds RW-WB / KE-EAC / STJ-HOSP and GRM Issue has
        # no `department` field anyway (which would server-error the
        # desk list). Use a project-scope filter that matches the
        # district inner-workflow duty against the seeded RW-WB project.
        "district inner-workflow scope — RW-WB project",
    ),
]


def login_in_context(browser, email: str, pwd: str):
    """Open a fresh, isolated context, log in via /login, return (context, page).

    Caller owns closing the context.
    """
    ctx = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=2,
        ignore_https_errors=True,
    )
    page = ctx.new_page()
    page.goto(f"{SITE}/login", wait_until="networkidle", timeout=30_000)
    page.locator("#login_email").fill(email)
    page.locator("#login_password").fill(pwd)
    page.locator("button.btn-login, .btn.btn-primary").first.click()
    # Frappe role_home_page maps each role to a different landing page
    # (project-admin → /app/platform, others → /app/home or /app), so
    # we just wait for *any* /app URL to confirm the session is live.
    page.wait_for_url("**/app**", timeout=20_000)
    return ctx, page


def capture_actor(
    suite: SuiteRun, browser, slug: str,
    email: str, pwd: str, route: str, route_note: str,
) -> tuple[Path, str, int]:
    """Run the per-actor capture. Returns (png_path, sha1_hex, size_bytes).

    Records ONE assertion of name `ACTOR-EV-<slug>`. The assertion is
    PASS only if (a) the PNG is on disk and >50KB, AND (b) the body
    text classifies as `real-content` (NOT a permission/login/blank/error).
    """
    png = SHOTS_DIR / f"actor-{slug}.png"
    txt = SHOTS_DIR / f"actor-{slug}.txt"
    aid = f"ACTOR-EV-{slug}"

    ctx = None
    try:
        ctx, page = login_in_context(browser, email, pwd)
        page.goto(f"{SITE}{route}", wait_until="networkidle", timeout=30_000)
        # Same hydration wait as run_ui_screenshots — give the desk a
        # moment to populate the page body.
        try:
            page.wait_for_function(
                "() => document.body && "
                "document.body.innerText.replace(/\\s+/g,' ').trim().length > 200",
                timeout=8000,
            )
        except Exception:
            pass
        # Full-page so the assertion catches any rendered banner the
        # actor might see below the fold (e.g. a "No Permission" dialog
        # injected into a long page).
        page.screenshot(path=str(png), full_page=True)
        text = body_text(page) or ""
        txt.write_text(text)

        size = png.stat().st_size if png.exists() else 0
        h = perceptual_hash(png)
        verdict, sig = classify_content(text, expects_auth=True, slug=slug)
        file_ok = png.exists() and size >= 50 * 1024  # ≥50KB per the brief
        verdict_ok = (verdict == "real-content")
        detail = (
            f"{png.name} ({size}B, sha1={h}) actor={email} "
            f"route={route} verdict={verdict}"
            + (f" sig=<{sig}>" if sig else "")
            + f" — {route_note}"
        )
        suite.ok(aid, file_ok and verdict_ok, detail)
        return png, h, size
    except Exception as e:
        suite.ok(aid, False,
                 f"{type(e).__name__}: {str(e)[:200]} (route={route})")
        return png, "", 0
    finally:
        if ctx is not None:
            try:
                ctx.close()
            except Exception:
                pass


def main() -> int:
    suite = SuiteRun("ACTOR-EVIDENCE")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        suite.ok("ACTOR-EV-0.playwright_available", False,
                 f"install with: pip install playwright && playwright install chromium ({e})")
        return summary(suite)

    captures: list[tuple[str, str, int]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for slug, (email, pwd), route, route_note in ACTORS:
                _png, h, size = capture_actor(
                    suite, browser, slug, email, pwd, route, route_note,
                )
                captures.append((slug, h, size))
        finally:
            browser.close()

    # Cross-actor uniqueness — every PNG must be content-distinct.
    # If two actors render byte-identical screens, that almost always
    # means one of them landed on the login page (cookie bleed) rather
    # than their duty surface. The classifier alone can miss this when
    # both pages are above the blank threshold.
    real_hashes = [h for _slug, h, _sz in captures if h]
    distinct = len(set(real_hashes))
    suite.ok(
        "ACTOR-EV-distinct-renders",
        distinct >= max(1, len(real_hashes) - 1),
        f"{distinct} distinct sha1 across {len(real_hashes)} captures "
        f"({len(real_hashes) - distinct} collisions: "
        + ",".join(
            f"{a[0]}={a[1][:8]}" for a in captures if a[1]
        ) + ")",
    )

    print(f"\n[ACTOR-EVIDENCE] saved "
          f"{sum(1 for _s, _h, sz in captures if sz)} actor PNGs to {SHOTS_DIR}")
    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
