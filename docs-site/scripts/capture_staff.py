"""Capture the staff (desk) side of eGRM for the role guides.

The demo accounts render the desk in Kinyarwanda. We try, in order, a `lang`
query param and a `preferred_language` cookie to get English without mutating
any user record — if neither works the shots stay in Kinyarwanda and the guide
has to say so rather than pretend otherwise.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE = os.environ.get("EGRM_BASE", "https://egrm.risa.gov.rw")
USER = os.environ["EGRM_USER"]
PASS = os.environ["EGRM_PASS"]
OUT = Path(__file__).resolve().parent.parent / "content" / "docs" / "img"
VIEWPORT = {"width": 1440, "height": 900}

# Strings that only exist in the English desk build.
EN_MARKERS = ("Search", "Notifications", "Open Issues", "Record Issue", "My Assignments")
RW_MARKERS = ("Shakisha", "Imenyekanisha", "Ibibazo Bifunguye", "Andika Ikibazo")


def snap(page, slug, settle=2500):
	page.wait_for_timeout(settle)
	dest = OUT / f"{slug}.png"
	page.screenshot(path=str(dest))
	print(f"  OK   {slug:26s} {dest.stat().st_size/1024:7.1f} KB")


def detect_lang(page):
	body = page.inner_text("body")
	en = sum(m in body for m in EN_MARKERS)
	rw = sum(m in body for m in RW_MARKERS)
	return "en" if en > rw else "rw"


def goto(page, path):
	try:
		page.goto(BASE + path, wait_until="networkidle", timeout=60000)
	except PWTimeout:
		page.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
	page.wait_for_timeout(2500)


def main():
	OUT.mkdir(parents=True, exist_ok=True)
	with sync_playwright() as p:
		try:
			browser = p.chromium.launch(headless=False, channel="chrome")
		except Exception:
			browser = p.chromium.launch(headless=False)
		ctx = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True)
		ctx.add_cookies(
			[{"name": "preferred_language", "value": "en", "domain": "egrm.risa.gov.rw", "path": "/"}]
		)
		page = ctx.new_page()

		print("== sign in ==")
		page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=45000)
		page.fill("#login_email", USER)
		page.fill("#login_password", PASS)
		page.click("button.btn-login")
		page.wait_for_url("**/app/**", timeout=60000)
		print(f"  signed in as {USER}")

		goto(page, "/app/egrm?lang=en")
		lang = detect_lang(page)
		print(f"  desk language after lang=en + cookie: {lang}")

		snap(page, "desk-workspace")

		print("== issue list ==")
		goto(page, "/app/grm-issue")
		snap(page, "issue-list")

		# Open the first real issue so the guide can show a populated record.
		opened = None
		try:
			href = page.locator(".list-row a[href*='/app/grm-issue/']").first.get_attribute("href")
			if href:
				opened = href
				goto(page, href if href.startswith("/") else "/" + href)
				snap(page, "issue-detail")
				print(f"  opened {href}")
		except Exception as e:
			print("  WARN could not open an issue:", str(e)[:160])

		print("== new issue form ==")
		goto(page, "/app/grm-issue/new")
		snap(page, "issue-new")

		print("== my assignments / open issues shortcuts ==")
		for slug, path in (
			("issue-open", "/app/grm-issue?status=Open"),
			("issue-assigned", "/app/grm-issue?assignee=" + USER),
		):
			goto(page, path)
			snap(page, slug)

		print(f"\nfinal desk language: {lang}; issue opened: {opened}")
		browser.close()
	return 0


if __name__ == "__main__":
	sys.exit(main())
