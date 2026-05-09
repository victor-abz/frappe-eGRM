"""One-shot helper: re-capture only wizard_step_12.png after a heal.

Drives the same playwright flow as run_ui_screenshots.py but targets a
single step so we can tighten the heal-and-verify loop on Step 12
(activation pre-flight checkbox row).
"""
from __future__ import annotations

import sys
from pathlib import Path

from _common import ACTOR_PROJECT_ADMIN, ART, SITE

VIEWPORT = {"width": 1440, "height": 900}
SHOTS_DIR = ART / "screenshots" / "wizard_steps"
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"playwright missing: {e}", file=sys.stderr)
        return 2

    step = 12
    out = SHOTS_DIR / f"wizard_step_{step:02d}.png"
    txt_out = SHOTS_DIR / f"wizard_step_{step:02d}.txt"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=2, ignore_https_errors=True,
        )
        page = ctx.new_page()
        email, pwd = ACTOR_PROJECT_ADMIN

        page.goto(f"{SITE}/login", wait_until="networkidle", timeout=30_000)
        page.locator("#login_email").fill(email)
        page.locator("#login_password").fill(pwd)
        page.locator("button.btn-login, .btn.btn-primary").first.click()
        page.wait_for_url("**/app**", timeout=20_000)
        print("login ok")

        url = (
            f"{SITE}/app/grm-project-wizard"
            f"?project=RW-WB&aqe_force_step={step}&_cb={int(__import__('time').time())}"
        )
        page.goto(url, wait_until="networkidle", timeout=30_000)
        try:
            page.wait_for_selector(".grm-wizard", timeout=8000)
            page.wait_for_function(
                "() => {"
                "  const t = document.querySelector('.grm-wizard-title');"
                f"  return t && t.textContent.startsWith('{step}.');"
                "}",
                timeout=8000,
            )
        except Exception as e:
            print(f"wait_for_function: {e}")

        # Hard-reload the page to pick up the freshly edited JS bundle
        # (Frappe serves /assets/<app>/js/page/<name>/<name>.js straight
        # from the file system but the browser cache is aggressive).
        page.evaluate("() => location.reload(true)")
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
            page.wait_for_function(
                "() => {"
                "  const t = document.querySelector('.grm-wizard-title');"
                f"  return t && t.textContent.startsWith('{step}.');"
                "}",
                timeout=10_000,
            )
        except Exception as e:
            print(f"reload-wait: {e}")

        body_loc = None
        for sel in (".grm-project-wizard .wizard-body",
                    ".grm-project-wizard", ".grm-wizard",
                    ".layout-main-section .page-body",
                    ".layout-main-section"):
            loc = page.locator(sel).first
            try:
                if loc.count() > 0 and loc.is_visible():
                    body_loc = loc
                    break
            except Exception:
                continue
        if body_loc is not None:
            body_loc.screenshot(path=str(out))
            print(f"wrote {out} (body-only)")
        else:
            page.screenshot(path=str(out), full_page=True)
            print(f"wrote {out} (full-page fallback)")

        text = ""
        try:
            text = page.locator("body").inner_text(timeout=4000)
        except Exception:
            pass
        txt_out.write_text(text or "")
        print(f"wrote {txt_out} ({len(text)} chars)")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
