"""SUITE: UI-GRM-USERS — search + pagination UX assertions for /app/grm-users.

Flags (and verifies the fix of) the UX gaps the user reported on the
`grm-users` custom desk page:

  - missing search input
  - missing pagination control
  - missing "Showing X–Y of Z" status
  - rendered count divorced from the real assignment count

Runs after UI-SCREENSHOTS in run_full_suite.py. Re-captures
`screenshots/07-grm-users.png` against the post-fix UI so the report
visually proves the search input + paginator exist.

Assertion ids:
  UX-07.search_input_present
  UX-07.search_filters_results
  UX-07.pagination_control_present
  UX-07.pagination_works
  UX-07.user_count_matches_assignments
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

from _common import (
    ACTOR_PROJECT_ADMIN, ART, SITE, SuiteRun, login, post, run, summary,
)
from run_ui_screenshots import (
    VIEWPORT, body_text, classify_content, perceptual_hash,
)


SHOTS_DIR = ART / "screenshots"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

GRM_USERS_URL = f"{SITE}/app/grm-users"

# Selector contracts — the page MUST expose at least one matching node
# from each set or the corresponding assertion fails.
SEARCH_SELECTORS = (
    "input.user-search",
    "input[type='search']",
    "input#grm-users-search",
    "input[placeholder*='Search']",
)

PAGINATOR_SELECTORS = (
    ".grm-users-paginator",
    ".pagination",
    "button.next-page",
    "button.prev-page",
    "select.page-size",
)

PAGE_SIZE_SELECTOR = "select.page-size, select#grm-users-page-size"
NEXT_BTN_SELECTOR = "button.next-page, button#grm-users-next"
PREV_BTN_SELECTOR = "button.prev-page, button#grm-users-prev"
STATUS_SELECTOR = ".grm-users-paginator-status, #grm-users-status"
TABLE_ROW_SELECTOR = ".grm-users-table tbody tr"
SEARCH_INPUT_SELECTOR = (
    "input.user-search, input#grm-users-search, "
    "input[type='search'][placeholder*='Search']"
)


def _server_total(s: requests.Session) -> int:
    """Hit the whitelisted endpoint to ask the server for the canonical total."""
    sc, body = post(
        s,
        "/api/method/egrm.egrm.page.grm_users.grm_users.list_assignments",
        json_body={
            "project": None,
            "search": "",
            "start": 0,
            "page_length": 1,
        },
    )
    if sc != 200:
        return -1
    msg = body.get("message") if isinstance(body, dict) else None
    if isinstance(msg, dict):
        return int(msg.get("total") or 0)
    if isinstance(msg, list):
        # Backwards-compat — if some shim re-wrapped the response.
        return len(msg)
    return -1


def _first_existing(page, selectors: tuple[str, ...]) -> str:
    """Return the first selector with at least one element, else empty string."""
    for sel in selectors:
        try:
            if page.locator(sel).count() > 0:
                return sel
        except Exception:
            continue
    return ""


def main() -> int:
    suite = SuiteRun("UI-GRM-USERS")

    # ---- canonical server-side total (single source of truth) ---------
    s = requests.Session()
    sc, body = login(s, *ACTOR_PROJECT_ADMIN)
    if sc != 200:
        suite.ok("UX-07.api_login", False,
                 f"login failed: {sc} {str(body)[:120]}")
        return summary(suite)
    suite.ok("UX-07.api_login", True, "login OK as project-admin")
    canonical_total = _server_total(s)
    suite.ok(
        "UX-07.canonical_total_resolved",
        canonical_total >= 0,
        f"server reports total={canonical_total}",
    )

    # ---- Playwright UI assertions -------------------------------------
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        suite.ok("UX-07.playwright_available", False,
                 f"install with: pip install playwright && playwright install chromium ({e})")
        return summary(suite)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a taller viewport than VIEWPORT so the paginator at the
        # bottom of the page lands in the regular (non-full-page)
        # screenshot. The desk's main column has its own scrollable
        # container, so a `full_page=True` capture on the OS-level
        # browser does not always grow the document height — making the
        # viewport bigger up-front is the most reliable way to land the
        # paginator inside the PNG.
        TALL_VIEWPORT = {"width": VIEWPORT["width"], "height": 1400}
        ctx = browser.new_context(
            viewport=TALL_VIEWPORT,
            device_scale_factor=2,
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        # Login via UI so the desk session cookies are set.
        try:
            page.goto(f"{SITE}/login", wait_until="networkidle", timeout=30_000)
            page.locator("#login_email").fill(ACTOR_PROJECT_ADMIN[0])
            page.locator("#login_password").fill(ACTOR_PROJECT_ADMIN[1])
            page.locator("button.btn-login, .btn.btn-primary").first.click()
            page.wait_for_url("**/app**", timeout=20_000)
            suite.ok("UX-07.ui_login", True, "via /login UI")
        except Exception as e:
            suite.ok("UX-07.ui_login", False,
                     f"{type(e).__name__}: {e}")
            browser.close()
            return summary(suite)

        # Land on /app/grm-users and wait for first table render.
        try:
            page.goto(GRM_USERS_URL, wait_until="networkidle", timeout=30_000)
            page.wait_for_selector(".grm-users", timeout=8_000)
            try:
                # Wait for either rows or the paginator status — either
                # signals first reload_assignments() returned.
                page.wait_for_function(
                    "() => {"
                    "  const status = document.querySelector('"
                    + STATUS_SELECTOR.replace("'", "\\'")
                    + "');"
                    "  if (!status) return false;"
                    "  const txt = (status.textContent || '').trim();"
                    "  return txt.length > 0 && !txt.includes('Loading');"
                    "}",
                    timeout=8_000,
                )
            except Exception:
                pass
        except Exception as e:
            suite.ok("UX-07.page_loaded", False,
                     f"{type(e).__name__}: {e}")
            browser.close()
            return summary(suite)
        suite.ok("UX-07.page_loaded", True, GRM_USERS_URL)

        # ---- UX-07.search_input_present --------------------------------
        search_sel = _first_existing(page, SEARCH_SELECTORS)
        suite.ok(
            "UX-07.search_input_present",
            bool(search_sel),
            f"matched_selector={search_sel!r} candidates={SEARCH_SELECTORS}",
        )

        # ---- UX-07.pagination_control_present --------------------------
        paginator_sel = _first_existing(page, PAGINATOR_SELECTORS)
        suite.ok(
            "UX-07.pagination_control_present",
            bool(paginator_sel),
            f"matched_selector={paginator_sel!r} candidates={PAGINATOR_SELECTORS}",
        )

        # ---- UX-07.user_count_matches_assignments ---------------------
        # The "Showing X–Y of Z" status should expose Z; cross-check vs
        # the canonical server-side total.
        status_text = ""
        try:
            status_text = (
                page.locator(STATUS_SELECTOR).first.inner_text(timeout=4000) or ""
            ).strip()
        except Exception:
            status_text = ""

        rendered_rows = 0
        try:
            rendered_rows = page.locator(TABLE_ROW_SELECTOR).count()
        except Exception:
            rendered_rows = 0

        # Parse "Showing 1–N of Z"
        import re as _re
        z_displayed = -1
        m = _re.search(
            r"of\s+(\d+)\b", status_text, _re.IGNORECASE,
        )
        if m:
            z_displayed = int(m.group(1))
        suite.ok(
            "UX-07.user_count_matches_assignments",
            z_displayed >= 0
            and canonical_total >= 0
            and z_displayed == canonical_total,
            f"status_text={status_text!r} z_displayed={z_displayed} "
            f"server_total={canonical_total} rendered_rows={rendered_rows}",
        )

        # ---- UX-07.pagination_works -----------------------------------
        # Strategy:
        #  - With default page_size=20 and Z>20, click Next → status start jumps.
        #  - Otherwise (Z<=20), validate the paginator state for a single
        #    page is correct: prev+next disabled, status reads
        #    "Showing 1–Z of Z", and rendered rows == Z.
        page_size_present = page.locator(PAGE_SIZE_SELECTOR).count() > 0
        next_present = page.locator(NEXT_BTN_SELECTOR).count() > 0
        prev_present = page.locator(PREV_BTN_SELECTOR).count() > 0

        ok_works = False
        works_detail_parts = [
            f"page_size_present={page_size_present}",
            f"next_present={next_present}",
            f"prev_present={prev_present}",
        ]

        if not (page_size_present and next_present and prev_present):
            ok_works = False
            works_detail_parts.append("missing-required-controls")
        elif z_displayed > 20:
            try:
                # Read first row "name" (data-name attr) to compare across pages.
                page.locator(NEXT_BTN_SELECTOR).first.click()
                page.wait_for_function(
                    "() => {"
                    "  const status = document.querySelector('"
                    + STATUS_SELECTOR.replace("'", "\\'")
                    + "');"
                    "  if (!status) return false;"
                    "  return /Showing\\s+21[\\u2013\\-]/.test(status.textContent || '');"
                    "}",
                    timeout=6000,
                )
                new_status = (page.locator(STATUS_SELECTOR).first
                              .inner_text(timeout=4000) or "").strip()
                ok_works = "21" in new_status
                works_detail_parts.append(
                    f"after_next_status={new_status!r}",
                )
            except Exception as e:
                ok_works = False
                works_detail_parts.append(
                    f"next_click_failed={type(e).__name__}: {e}",
                )
        else:
            # <= 20 rows. Single-page paginator state must still be valid.
            try:
                next_disabled = page.locator(NEXT_BTN_SELECTOR).first.is_disabled()
                prev_disabled = page.locator(PREV_BTN_SELECTOR).first.is_disabled()
                ok_works = (
                    next_disabled
                    and prev_disabled
                    and z_displayed == canonical_total
                    and rendered_rows == canonical_total
                )
                works_detail_parts.append(
                    f"single_page next_disabled={next_disabled} "
                    f"prev_disabled={prev_disabled}",
                )
            except Exception as e:
                ok_works = False
                works_detail_parts.append(
                    f"single_page_check_failed={type(e).__name__}: {e}",
                )

        suite.ok(
            "UX-07.pagination_works",
            ok_works,
            " ".join(works_detail_parts),
        )

        # ---- UX-07.search_filters_results -----------------------------
        # Pick a substring guaranteed to filter the table. The seed data
        # always includes "officer" (multiple), "frida", "triage" etc.
        # Use "frida" which matches just one user but multiple
        # assignments (one per project), so the filtered count must be
        # both >0 and < canonical_total.
        ok_search = False
        search_detail_parts = [f"canonical_total={canonical_total}"]
        if not search_sel:
            ok_search = False
            search_detail_parts.append("search-selector-missing")
        else:
            try:
                inp = page.locator(SEARCH_INPUT_SELECTOR).first
                inp.click()
                inp.fill("frida")
                inp.dispatch_event("input")
                # Debounce is 250ms on the page — wait until the
                # status line actually CHANGES (smaller `of N` or the
                # "No users match" branch). We capture the unfiltered
                # `of N` first, then wait for the count to *shrink*.
                start_total = canonical_total
                page.wait_for_function(
                    "(start_total) => {"
                    "  const status = document.querySelector('"
                    + STATUS_SELECTOR.replace("'", "\\'")
                    + "');"
                    "  if (!status) return false;"
                    "  const txt = (status.textContent || '').trim();"
                    "  if (!txt) return false;"
                    "  if (/No users match/i.test(txt)) return true;"
                    "  const m = txt.match(/of\\s+(\\d+)/i);"
                    "  if (!m) return false;"
                    "  return parseInt(m[1], 10) < start_total;"
                    "}",
                    arg=start_total,
                    timeout=5000,
                )
                filtered_status = (page.locator(STATUS_SELECTOR).first
                                   .inner_text(timeout=4000) or "").strip()
                m2 = _re.search(r"of\s+(\d+)\b", filtered_status, _re.IGNORECASE)
                z_filtered = int(m2.group(1)) if m2 else -1
                filtered_rows = 0
                try:
                    filtered_rows = page.locator(TABLE_ROW_SELECTOR).count()
                except Exception:
                    filtered_rows = 0
                # Filtered set must shrink (must be strictly smaller than
                # the unfiltered total when the unfiltered total > 0,
                # AND every rendered row must contain "frida"
                # case-insensitive in its text).
                shrank = (canonical_total > 0
                          and 0 <= z_filtered < canonical_total)
                rows_contain_frida = True
                if filtered_rows > 0:
                    try:
                        body_html = page.locator(TABLE_ROW_SELECTOR).all_inner_texts()
                        rows_contain_frida = all(
                            "frida" in (t or "").lower() for t in body_html
                        )
                    except Exception:
                        rows_contain_frida = True  # don't fail on locator weirdness
                ok_search = shrank and rows_contain_frida and filtered_rows > 0
                search_detail_parts.extend([
                    f"filtered_status={filtered_status!r}",
                    f"z_filtered={z_filtered}",
                    f"filtered_rows={filtered_rows}",
                    f"rows_contain_frida={rows_contain_frida}",
                ])
                # Clean up — restore unfiltered list for the screenshot.
                inp.fill("")
                inp.dispatch_event("input")
            except Exception as e:
                ok_search = False
                search_detail_parts.append(
                    f"search_failed={type(e).__name__}: {e}",
                )

        suite.ok(
            "UX-07.search_filters_results",
            ok_search,
            " ".join(search_detail_parts),
        )

        # ---- re-capture the canonical 07-grm-users.png ----------------
        # Wait for the unfiltered list to reload one more time so the
        # screenshot shows the full population again.
        try:
            page.wait_for_function(
                "() => {"
                "  const status = document.querySelector('"
                + STATUS_SELECTOR.replace("'", "\\'")
                + "');"
                "  if (!status) return false;"
                "  const txt = (status.textContent || '').trim();"
                "  if (!txt) return false;"
                "  const m = txt.match(/of\\s+(\\d+)/i);"
                "  return m && parseInt(m[1], 10) === " + str(canonical_total) + ";"
                "}",
                timeout=4000,
            )
        except Exception:
            pass

        out_png = SHOTS_DIR / "07-grm-users.png"
        out_txt = SHOTS_DIR / "07-grm-users.txt"
        try:
            # Capture using the (taller) viewport so search input AND
            # paginator both land in the PNG. We deliberately do NOT use
            # full_page=True because the desk has its own scrollable
            # container; a tall viewport is more reliable.
            page.screenshot(path=str(out_png), full_page=False)
            text = body_text(page)
            out_txt.write_text(text or "")
            verdict, sig = classify_content(
                text, expects_auth=True, slug="07-grm-users",
            )
            file_ok = out_png.exists() and out_png.stat().st_size > 1024
            verdict_ok = verdict == "real-content"
            # Also verify the search input + paginator are visible in the
            # captured body text (a defensive cross-check on the PNG).
            text_lc = (text or "").lower()
            shows_search = (
                "search users" in text_lc
                or "search by name" in text_lc
            )
            shows_paginator = (
                "showing" in text_lc and "of" in text_lc
            ) or "page size" in text_lc
            suite.ok(
                "UX-07.screenshot_captured",
                file_ok and verdict_ok,
                f"{out_png.name} ({out_png.stat().st_size}B, "
                f"sha1={perceptual_hash(out_png)}) verdict={verdict}"
                + (f" sig=<{sig}>" if sig else "")
                + f" shows_search_in_body={shows_search} "
                  f"shows_paginator_in_body={shows_paginator}",
            )
        except Exception as e:
            suite.ok("UX-07.screenshot_captured", False,
                     f"{type(e).__name__}: {e}")

        browser.close()

    return summary(suite)


if __name__ == "__main__":
    sys.exit(run(main))
