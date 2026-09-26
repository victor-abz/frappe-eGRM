"""Walk the citizen portal in English and capture every step of the submit wizard.

Deliberately stops before the final submit — this runs against the live demo
server and must not create a grievance that pollutes the demo data.

The portal ships English, French and Kinyarwanda; the language control is a
plain `<select id="portal-language">`, so we set it directly rather than
clicking through a menu.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("EGRM_BASE", "https://egrm.risa.gov.rw")
LANG = os.environ.get("EGRM_LANG", "en")
OUT = Path(__file__).resolve().parent.parent / "content" / "docs" / "img"
VIEWPORT = {"width": 1440, "height": 900}


def snap(page, slug):
	page.wait_for_timeout(1200)
	dest = OUT / f"{slug}.png"
	page.screenshot(path=str(dest))
	print(f"  OK   {slug:26s} {dest.stat().st_size/1024:7.1f} KB")


def set_language(page, lang):
	for sel in page.locator("select").all():
		try:
			if "portal-language" in (sel.get_attribute("id") or "") or "English" in sel.inner_text():
				sel.select_option(lang)
				page.wait_for_timeout(1500)
		except Exception:
			continue


def continue_btn(page):
	for name in ("Continue", "Next", "Komeza", "Suivant"):
		btn = page.get_by_role("button", name=name)
		if btn.count():
			return btn.first, name
	return None, None


def advance(page, step):
	btn, name = continue_btn(page)
	if btn and btn.is_enabled():
		btn.click()
		page.wait_for_timeout(1800)
		print(f"  -> step {step} (via '{name}')")
		return True
	print(f"  STUCK before step {step}; buttons =", page.locator("button").all_inner_texts())
	return False


def fill_region_cascade(page):
	"""Select the first real option of each region dropdown, following the cascade."""
	for _ in range(6):
		selects = [
			s
			for s in page.locator("select").all()
			if (s.get_attribute("id") or "") != "portal-language" and "English" not in s.inner_text()
		]
		progressed = False
		for sel in selects:
			try:
				if sel.input_value():
					continue  # already chosen
				values = [o for o in sel.evaluate("s => [...s.options].map(o => o.value)") if o]
				if values:
					sel.select_option(values[0])
					page.wait_for_timeout(1200)
					progressed = True
			except Exception:
				continue
		if not progressed:
			break


def main():
	OUT.mkdir(parents=True, exist_ok=True)
	with sync_playwright() as p:
		try:
			browser = p.chromium.launch(headless=False, channel="chrome")
		except Exception:
			browser = p.chromium.launch(headless=False)
		page = browser.new_context(viewport=VIEWPORT, ignore_https_errors=True).new_page()

		print(f"== home ({LANG}) ==")
		page.goto(f"{BASE}/grm-portal", wait_until="networkidle", timeout=60000)
		page.wait_for_timeout(2000)
		set_language(page, LANG)
		snap(page, "portal-home-en")

		print("== submit wizard ==")
		page.goto(f"{BASE}/grm-portal/submit", wait_until="networkidle", timeout=60000)
		page.wait_for_timeout(2000)
		set_language(page, LANG)
		snap(page, "submit-step1")

		for label in ("Complaint", "Web Form"):
			try:
				page.get_by_text(label, exact=True).first.click(timeout=5000)
				page.wait_for_timeout(500)
			except Exception as e:
				print(f"  WARN select {label}:", str(e)[:100])
		snap(page, "submit-step1-filled")

		if advance(page, 2):
			snap(page, "submit-step2")
			fill_region_cascade(page)
			snap(page, "submit-step2-filled")

			if advance(page, 3):
				snap(page, "submit-step3")
				# Step 3 is the description; fill whatever text inputs exist.
				texts = page.locator("input[type=text], textarea").all()
				values = [
					"Water point not working in our village",
					"The community water point has been broken for three weeks. "
					"Families now walk 4 km to fetch water.",
				]
				for box, val in zip(texts, values, strict=False):
					try:
						box.fill(val)
					except Exception:
						pass
				page.wait_for_timeout(800)
				snap(page, "submit-step3-filled")

				if advance(page, 4):
					snap(page, "submit-step4")
					print("  reached final step — NOT submitting (live demo data)")

		print("== track / login ==")
		page.goto(f"{BASE}/grm-portal/track", wait_until="networkidle", timeout=60000)
		page.wait_for_timeout(1500)
		set_language(page, LANG)
		snap(page, "portal-track-en")

		page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
		snap(page, "login-en")

		browser.close()
	return 0


if __name__ == "__main__":
	sys.exit(main())
