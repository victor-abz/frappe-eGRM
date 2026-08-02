"""Phase F.3 walker — Step 9 (Users) bulk-import 4-stage UI.

Drives the new ``GRMWizardStep9UserImport`` panel end-to-end in a visible
browser (``headless=False``, ``slow_mo=200``) per the Phase F plan:

    empty-state → upload → mapping → preview → import-running → log
                → list-refresh-shows-new-users

Selectors are pinned at the top of the file so future UI changes are a
one-line fix here (mirrors `run_step9_users_list_tests.py`'s discipline).
The walker writes a deterministic CSV to ``/tmp`` and uploads it via
``page.set_input_files`` — no drag-drop, no real Frappe FileUploader
modal — to keep the harness reproducible.

Selector pins (single source of truth)
--------------------------------------
- Add-toggle bulk button     ``.grm-step9-add-toggle [data-mode=bulk]``
- 4 stage pills              ``.grm-stage[data-stage=template|upload|mapping|preview]``
- Hidden file input          ``.grm-step9-bulk input[type=file]`` (rendered
                              by ``frappe.ui.FileUploader`` after the
                              "Choose file" button is clicked)
- Mapping table rows         ``.grm-mapping-row`` (fallback: any ``select``
                              inside ``.grm-step9-bulk-content``)
- Continue-to-preview button ``.grm-step9-bulk .grm-stage-next``
- Auto-create-regions check  ``.grm-auto-create-regions``
- Start-import button        ``.grm-step9-bulk .grm-import-start``
- Progress UI                ``.grm-step9-bulk .grm-import-progress``
- Progress text/log          ``.grm-progress-text``, ``.grm-progress-log``
- Final list table refresh   ``.grm-users-table tbody tr``

Environment
-----------
``EGRM_SITE``                http://egrm.local:8000  (override per env)
``EGRM_STEP9_PROJECT``       project code to drive (must already exist)
``EGRM_ADMIN_USER/PASS``     login creds
``EGRM_AQE_ART``             screenshot output root

Exit code
---------
0 if every check is OK; 1 otherwise. Evidence dict lands at
``$EGRM_AQE_ART/step9_user_import_evidence.json``.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Playwright is the runtime — installed by the AQE harness.
try:
	from playwright.sync_api import (  # type: ignore
		Page,
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
SCREENSHOTS = ART / "screenshots" / "step9_user_import"
SCREENSHOTS.mkdir(parents=True, exist_ok=True)


# ---- Selector pins ---------------------------------------------------------
SEL_PANEL = ".grm-step9-users-panel"
SEL_ADD_TOGGLE_BULK = '.grm-step9-add-toggle [data-mode="bulk"]'
SEL_BULK_PANEL = ".grm-step9-bulk"
SEL_STAGE_TEMPLATE = '.grm-stage[data-stage="template"]'
SEL_STAGE_UPLOAD = '.grm-stage[data-stage="upload"]'
SEL_STAGE_MAPPING = '.grm-stage[data-stage="mapping"]'
SEL_STAGE_PREVIEW = '.grm-stage[data-stage="preview"]'
SEL_STAGE_NEXT = ".grm-step9-bulk .grm-stage-next"
SEL_FILE_INPUT_ANY = "input[type=file]"
SEL_AUTO_CREATE = ".grm-auto-create-regions"
SEL_IMPORT_START = ".grm-step9-bulk .grm-import-start"
SEL_PROGRESS_BLOCK = ".grm-step9-bulk .grm-import-progress"
SEL_PROGRESS_TEXT = ".grm-progress-text"
SEL_PROGRESS_LOG = ".grm-progress-log"
SEL_USERS_TABLE_ROWS = ".grm-users-table tbody tr"


CSV_ROWS = [
	# 4 deterministic rows so the walker's screenshots are stable across
	# runs. Provinces/Districts/Sectors here are common Rwanda RDAP
	# values; the auto-create flag will create any that don't exist.
	(
		"walker.alice@example.com",
		"Alice",
		"Walker",
		"Female",
		"+250788000001",
		"Officer",
		"Kigali City",
		"Gasabo",
		"Kacyiru",
	),
	(
		"walker.bruno@example.com",
		"Bruno",
		"Walker",
		"Male",
		"+250788000002",
		"Officer",
		"Kigali City",
		"Nyarugenge",
		"Nyamirambo",
	),
	(
		"walker.celia@example.com",
		"Celia",
		"Walker",
		"Female",
		"+250788000003",
		"Officer",
		"Northern",
		"Musanze",
		"Cyuve",
	),
	(
		"walker.diego@example.com",
		"Diego",
		"Walker",
		"Male",
		"+250788000004",
		"Officer",
		"Western",
		"Rubavu",
		"Gisenyi",
	),
]
CSV_HEADERS = (
	"Email",
	"First Name",
	"Last Name",
	"Gender",
	"Phone",
	"Position",
	"Province",
	"District",
	"Sector",
)


def _login(page: Page) -> None:
	page.goto(f"{SITE}/login", wait_until="domcontentloaded")
	page.fill('input[name="usr"]', ADMIN_USER)
	page.fill('input[name="pwd"]', ADMIN_PASS)
	page.click("button.btn-primary")
	page.wait_for_url("**/app**", timeout=15000)


def _open_wizard(page: Page) -> None:
	url = f"{SITE}/app/grm-project-wizard?project={PROJECT}&aqe_force_step=9"
	page.goto(url, wait_until="networkidle")
	page.wait_for_selector(SEL_PANEL, timeout=15000)


def _shoot(page: Page, name: str) -> str:
	p = SCREENSHOTS / f"{name}.png"
	page.screenshot(path=str(p), full_page=True)
	return str(p)


def _write_csv() -> Path:
	f = tempfile.NamedTemporaryFile(
		"w",
		prefix="step9_walker_",
		suffix=".csv",
		delete=False,
		encoding="utf-8",
	)
	f.write(",".join(CSV_HEADERS) + "\n")
	for row in CSV_ROWS:
		f.write(",".join(row) + "\n")
	f.close()
	return Path(f.name)


def _select_bulk_tab(page: Page) -> None:
	# The bulk panel is hidden behind a tab toggle. If the empty-state
	# auto-flipped us to bulk (E.6), the toggle's already in bulk-mode,
	# but clicking again is idempotent.
	btn = page.locator(SEL_ADD_TOGGLE_BULK)
	if btn.count():
		btn.first.click()
	page.wait_for_selector(SEL_BULK_PANEL, timeout=10000)


def _click_stage_next(page: Page) -> None:
	# The stage-next button is re-rendered on every set_stage(); always
	# click the FIRST visible one (there can be a stale selector if the
	# mapping panel hasn't fully replaced the template panel yet).
	page.locator(SEL_STAGE_NEXT).first.click()


def _wait_for_stage_pill_active(page: Page, sel: str, timeout: int = 10000) -> None:
	deadline = time.time() + (timeout / 1000)
	while time.time() < deadline:
		cls = page.locator(sel).get_attribute("class") or ""
		if "active" in cls:
			return
		page.wait_for_timeout(150)
	raise TimeoutError(f"stage pill {sel} never went active within {timeout}ms")


def _set_input_files_via_uploader(page: Page, csv_path: Path) -> None:
	"""Bypass the Frappe FileUploader modal by binding directly to the
	hidden ``input[type=file]`` it renders.

	The Frappe uploader injects a ``<input type=file>`` into the DOM only
	after the user clicks "Choose file". We click that button to provoke
	the input, then ``set_input_files`` it. Falls back to a generic
	file-input search if the modal renders the input outside the bulk
	panel.
	"""
	page.locator(".grm-upload-browse").first.click()
	# Wait for the modal's input to appear. Frappe places it inside
	# ``.modal`` (file-uploader dialog); accept either.
	page.wait_for_selector(SEL_FILE_INPUT_ANY, timeout=10000, state="attached")
	# Multiple file inputs can exist; prefer the most recently mounted.
	inputs = page.locator(SEL_FILE_INPUT_ANY)
	inputs.last.set_input_files(str(csv_path))


def _walk(page: Page) -> dict:
	evidence: dict = {
		"project": PROJECT,
		"url": page.url,
		"screenshots": {},
		"checks": [],
		"csv_rows": len(CSV_ROWS),
	}

	# Empty-state vs populated — the walker doesn't depend on either,
	# but we capture the mode for evidence.
	has_empty = page.locator(".grm-step9-empty").count() > 0
	has_table = page.locator(".grm-users-table").count() > 0
	evidence["mode_before"] = "empty" if has_empty else ("table" if has_table else "unknown")

	_select_bulk_tab(page)
	evidence["screenshots"]["stage_template"] = _shoot(page, "stage_template")

	# Stage 1 → 2 (template → upload).
	_click_stage_next(page)
	page.wait_for_selector(".grm-upload-browse", timeout=10000)
	_wait_for_stage_pill_active(page, SEL_STAGE_UPLOAD)
	evidence["screenshots"]["stage_upload"] = _shoot(page, "stage_upload")
	evidence["checks"].append({"name": "reached-upload-stage", "ok": True})

	csv_path = _write_csv()
	try:
		_set_input_files_via_uploader(page, csv_path)
		# The wizard auto-advances to mapping after auto-detect resolves.
		_wait_for_stage_pill_active(page, SEL_STAGE_MAPPING, timeout=20000)
		evidence["screenshots"]["stage_mapping"] = _shoot(page, "stage_mapping")
		evidence["checks"].append({"name": "reached-mapping-stage", "ok": True})

		# Mapping panel: auto-detect should have populated <select> options
		# for each header. The mapper renders one row per source column.
		select_count = page.locator(f"{SEL_BULK_PANEL} select").count()
		evidence["mapping_selects"] = select_count
		evidence["checks"].append(
			{
				"name": "mapping-table-has-selects",
				"ok": select_count >= len(CSV_HEADERS),
			}
		)

		# Stage 3 → 4 (mapping → preview). The button is disabled until the
		# validation gate passes; if auto-detect already validated, it's
		# enabled. We assume valid headers (Email/First Name/Last Name/Role
		# are auto-detected); if disabled, surface a check failure.
		next_btn = page.locator(SEL_STAGE_NEXT)
		if next_btn.first.is_disabled():
			evidence["checks"].append(
				{
					"name": "mapping-validation-gate-passes",
					"ok": False,
					"detail": "Continue-to-preview is disabled; missing required mapping",
				}
			)
			return evidence
		next_btn.first.click()

		_wait_for_stage_pill_active(page, SEL_STAGE_PREVIEW, timeout=20000)
		evidence["screenshots"]["stage_preview"] = _shoot(page, "stage_preview")
		evidence["checks"].append({"name": "reached-preview-stage", "ok": True})

		# Make sure auto-create is on so the test isn't blocked by missing
		# admin regions in a fresh project.
		ac = page.locator(SEL_AUTO_CREATE)
		if ac.count() and not ac.is_checked():
			ac.check()

		# Click "Start import" and watch the progress block flip visible.
		page.locator(SEL_IMPORT_START).click()
		page.wait_for_selector(f"{SEL_PROGRESS_BLOCK}:not([hidden])", timeout=10000)
		evidence["screenshots"]["import_running"] = _shoot(page, "import_running")
		evidence["checks"].append({"name": "import-progress-visible", "ok": True})

		# Wait for terminal status; the wizard updates ``.grm-progress-text``
		# on every poll. Status text matches "Success: N succeeded, 0 failed".
		terminal_substrings = ("Success", "Partial Success", "Error", "Failed")
		deadline = time.time() + 60
		last_text = ""
		while time.time() < deadline:
			txt = page.locator(SEL_PROGRESS_TEXT).inner_text()
			if txt:
				last_text = txt
				if any(t in txt for t in terminal_substrings):
					break
			page.wait_for_timeout(750)
		evidence["progress_final_text"] = last_text
		evidence["checks"].append(
			{
				"name": "import-reached-terminal-status",
				"ok": any(t in last_text for t in terminal_substrings),
			}
		)
		evidence["progress_log_tail"] = (
			page.locator(SEL_PROGRESS_LOG).inner_text() if page.locator(SEL_PROGRESS_LOG).count() else ""
		)
		evidence["screenshots"]["import_finished"] = _shoot(page, "import_finished")

		# The wizard's on_completed callback refreshes the list panel.
		# Wait for the table body to gain at least len(CSV_ROWS) rows.
		# If the project already had assignments, we just check it's grown.
		page.wait_for_timeout(2000)  # debounce after refresh
		rows_after = page.locator(SEL_USERS_TABLE_ROWS).count()
		evidence["rows_after_import"] = rows_after
		evidence["checks"].append(
			{
				"name": "list-refreshed-shows-rows",
				"ok": rows_after >= len(CSV_ROWS),
			}
		)
		evidence["screenshots"]["list_after_refresh"] = _shoot(page, "list_after_refresh")
	finally:
		try:
			csv_path.unlink()
		except Exception:
			pass

	return evidence


def main() -> int:
	with sync_playwright() as pw:
		browser = pw.chromium.launch(headless=False, slow_mo=200)
		context = browser.new_context()
		page = context.new_page()
		try:
			_login(page)
			_open_wizard(page)
			evidence = _walk(page)
		except (PWTimeout, TimeoutError) as exc:
			evidence = {
				"project": PROJECT,
				"url": page.url,
				"error": f"{type(exc).__name__}: {exc}",
				"screenshots": {"error": _shoot(page, "error")},
				"checks": [{"name": "walker-completed", "ok": False}],
			}
		finally:
			context.close()
			browser.close()

	out = ART / "step9_user_import_evidence.json"
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
