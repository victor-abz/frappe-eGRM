"""Phase C.F walker — Step 9 (Users) existing-users list panel.

Smoke-tests the read-only side of the new Phase C list panel:

  1. Login + open the wizard at ``app/grm-project-wizard?project=RDAP&aqe_force_step=9``.
  2. Wait for the panel to mount (``.grm-step9-users-panel``).
  3. Branch on row count:
     - 0 rows → assert empty-state copy renders ("No users assigned…").
     - >0 rows → assert table headers + at least one pill render correctly.

The walker DOES NOT seed data. If RDAP has 0 assignments, only the empty
state is exercised — that's intentional per the Phase C plan (Phase F
covers the heavier integration scenarios).

Selectors pinned for stability:
  - Empty state           ─ ``.grm-step9-empty``
  - List title row        ─ ``.grm-step9-list-title``
  - Search input          ─ ``.grm-step9-search``
  - Filter dropdowns      ─ ``.grm-step9-level-filter``,
                            ``.grm-step9-role-filter``,
                            ``.grm-step9-status-filter``
  - Users table           ─ ``.grm-users-table``
  - Pills                 ─ ``.grm-pill[data-field=role]``, etc.

This file is intentionally self-contained (no _common imports) so it
can run before the broader AQE suite scaffolding lands on this branch;
when the suite re-imports, replace the inline LOGIN helper with
``_common.login`` and ``_common.SITE``.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Playwright is the runtime — installed by the AQE harness.
try:
	from playwright.sync_api import (  # type: ignore
		Page,
		expect,
		sync_playwright,
	)
	from playwright.sync_api import (
		TimeoutError as PWTimeout,
	)
except ImportError:  # pragma: no cover — caller installs Playwright.
	print("Playwright not installed. Run `pip install playwright && playwright install chromium`.")
	sys.exit(1)


SITE = os.environ.get("EGRM_SITE", "http://egrm.local:8000")
PROJECT = os.environ.get("EGRM_STEP9_PROJECT", "RDAP")
ADMIN_USER = os.environ.get("EGRM_ADMIN_USER", "Administrator")
ADMIN_PASS = os.environ.get("EGRM_ADMIN_PASS", "admin")

ART = Path(
	os.environ.get(
		"EGRM_AQE_ART",
		"/Users/victor/egrm/aqe-screenshots/aqe-full-suite",
	)
)
SCREENSHOTS = ART / "screenshots" / "step9_users_list"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


def _login(page: Page) -> None:
	page.goto(f"{SITE}/login", wait_until="domcontentloaded")
	page.fill('input[name="usr"]', ADMIN_USER)
	page.fill('input[name="pwd"]', ADMIN_PASS)
	page.click("button.btn-primary")
	page.wait_for_url("**/app**", timeout=15000)


def _open_wizard(page: Page) -> None:
	url = f"{SITE}/app/grm-project-wizard?project={PROJECT}&aqe_force_step=9"
	page.goto(url, wait_until="networkidle")
	# The composition mounts asynchronously; wait for either the empty
	# state or the table to appear.
	page.wait_for_selector(
		".grm-step9-users-panel",
		timeout=15000,
	)


def _take_screenshot(page: Page, name: str) -> str:
	path = SCREENSHOTS / f"{name}.png"
	page.screenshot(path=str(path), full_page=True)
	return str(path)


def _walk(page: Page) -> dict:
	"""Run the assertions; return a JSON-friendly evidence dict."""
	evidence: dict = {
		"project": PROJECT,
		"url": page.url,
		"screenshots": {},
		"checks": [],
	}

	# The list panel always renders one of: empty-state OR table.
	has_empty = page.locator(".grm-step9-empty").count() > 0
	has_table = page.locator(".grm-users-table").count() > 0

	evidence["mode"] = "empty" if has_empty else ("table" if has_table else "unknown")
	evidence["checks"].append(
		{
			"name": "panel-rendered",
			"ok": has_empty or has_table,
		}
	)

	if has_empty:
		empty_text = page.locator(".grm-step9-empty").inner_text()
		evidence["empty_text"] = empty_text
		evidence["checks"].append(
			{
				"name": "empty-state-copy",
				"ok": "No users assigned" in empty_text,
			}
		)
		evidence["screenshots"]["empty"] = _take_screenshot(page, "empty")
		return evidence

	if has_table:
		# Header columns we expect (pin against future regressions).
		headers = page.locator(".grm-users-table thead th").all_inner_texts()
		evidence["headers"] = headers
		evidence["checks"].append(
			{
				"name": "table-headers-include-role",
				"ok": any("Role" in h for h in headers),
			}
		)
		evidence["row_count"] = page.locator(".grm-users-table tbody tr").count()
		evidence["pill_count"] = page.locator(".grm-pill").count()
		evidence["checks"].append(
			{
				"name": "at-least-one-row",
				"ok": evidence["row_count"] > 0,
			}
		)
		evidence["checks"].append(
			{
				"name": "at-least-one-pill",
				"ok": evidence["pill_count"] > 0,
			}
		)
		evidence["screenshots"]["table"] = _take_screenshot(page, "table")

	return evidence


def main() -> int:
	with sync_playwright() as pw:
		browser = pw.chromium.launch(headless=True)
		context = browser.new_context()
		page = context.new_page()
		try:
			_login(page)
			_open_wizard(page)
			evidence = _walk(page)
		except PWTimeout as exc:
			evidence = {
				"project": PROJECT,
				"url": page.url,
				"error": f"PWTimeout: {exc}",
				"screenshots": {"error": _take_screenshot(page, "error")},
				"checks": [{"name": "panel-rendered", "ok": False}],
			}
		finally:
			context.close()
			browser.close()

	out = ART / "step9_users_list_evidence.json"
	out.write_text(json.dumps(evidence, indent=2))
	print(f"Wrote evidence → {out}")
	failed = [c for c in evidence.get("checks", []) if not c.get("ok")]
	if failed:
		print(f"FAILED checks: {failed}")
		return 1
	print("OK")
	return 0


if __name__ == "__main__":
	sys.exit(main())
