"""Capture user-guide screenshots from a live eGRM site.

Runs headed on purpose (project rule: browser work must be visible). Shots land
in `content/docs/img/` so the MDX pages can reference them relatively — fumadocs
imports relative images as modules, which is what keeps them working under the
site's `basePath`.

Usage:
    python3 scripts/capture.py                 # public pages only
    EGRM_USER=... EGRM_PASS=... python3 scripts/capture.py   # + signed-in pages
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

BASE = os.environ.get("EGRM_BASE", "https://egrm.risa.gov.rw")
USER = os.environ.get("EGRM_USER")
PASS = os.environ.get("EGRM_PASS")
OUT = Path(__file__).resolve().parent.parent / "content" / "docs" / "img"
VIEWPORT = {"width": 1440, "height": 900}

# (slug, path, wait_selector_or_None, full_page)
PUBLIC_SHOTS = [
	("portal-home", "/grm-portal", None, False),
	("portal-submit", "/grm-portal/submit", None, False),
	("portal-track", "/grm-portal/track", None, False),
	("portal-dashboard", "/grm-portal/dashboard", None, False),
	("login", "/login", "input", False),
]

PRIVATE_SHOTS = [
	("desk-workspace", "/app/egrm", None, False),
	("issue-list", "/app/grm-issue", None, False),
	("issue-new", "/app/grm-issue/new", None, False),
]


def shoot(page, slug, path, wait_for, full_page):
	url = BASE + path
	try:
		page.goto(url, wait_until="networkidle", timeout=45000)
	except PWTimeout:
		# networkidle never settles on pages that poll; the DOM is usually
		# ready well before that, so fall back rather than losing the shot.
		try:
			page.goto(url, wait_until="domcontentloaded", timeout=30000)
		except PWTimeout:
			print(f"  SKIP {slug}: page never loaded")
			return False
	if wait_for:
		try:
			page.wait_for_selector(wait_for, timeout=15000)
		except PWTimeout:
			pass
	page.wait_for_timeout(2500)
	dest = OUT / f"{slug}.png"
	page.screenshot(path=str(dest), full_page=full_page)
	size = dest.stat().st_size
	print(f"  OK   {slug:18s} {size/1024:7.1f} KB  <- {path}")
	return True


def main():
	OUT.mkdir(parents=True, exist_ok=True)
	captured, failed = [], []

	with sync_playwright() as p:
		# Prefer the system Chrome: Playwright's bundled chromium isn't
		# downloaded on this machine, and a 150 MB fetch isn't worth it for
		# screenshots of a plain web app.
		try:
			browser = p.chromium.launch(headless=False, channel="chrome")
		except Exception:
			browser = p.chromium.launch(headless=False)
		ctx = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True)
		page = ctx.new_page()

		print(f"== public pages @ {BASE} ==")
		for slug, path, wait_for, full in PUBLIC_SHOTS:
			(captured if shoot(page, slug, path, wait_for, full) else failed).append(slug)

		if USER and PASS:
			print("== signing in ==")
			page.goto(f"{BASE}/login", wait_until="domcontentloaded", timeout=45000)
			page.fill("#login_email", USER)
			page.fill("#login_password", PASS)
			page.click("button.btn-login")
			try:
				page.wait_for_url("**/app/**", timeout=45000)
				print(f"  signed in as {USER}")
			except PWTimeout:
				print(f"  WARN: login did not redirect to /app (at {page.url})")

			print("== signed-in pages ==")
			for slug, path, wait_for, full in PRIVATE_SHOTS:
				(captured if shoot(page, slug, path, wait_for, full) else failed).append(slug)
		else:
			print("== skipping signed-in pages (EGRM_USER/EGRM_PASS unset) ==")

		ctx.close()
		browser.close()

	print(f"\ncaptured={len(captured)} failed={len(failed)}")
	if failed:
		print("failed:", ", ".join(failed))
	return 1 if failed else 0


if __name__ == "__main__":
	sys.exit(main())
