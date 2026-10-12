import json
from pathlib import Path

import frappe
from frappe.translate import get_all_translations, get_language

no_cache = 1

# The portal renders ~191 distinct strings out of the ~1,470 in a translation
# file. Shipping just those inline costs a few KB and removes a round trip that
# the SPA otherwise cannot start without.
STRINGS_MANIFEST = Path(frappe.get_app_path("egrm")) / "portal_strings.json"


def _portal_strings() -> list[str]:
	"""The keys the SPA renders, as extracted by scripts/extract_portal_strings.py."""
	return frappe.cache().get_value(
		"egrm_portal_strings",
		generator=lambda: json.loads(STRINGS_MANIFEST.read_text(encoding="utf-8")),
		shared=True,
	)


def _inline_translations(lang: str) -> str:
	"""The portal's own strings for `lang`, as a JSON literal safe inside <script>.

	Without this the SPA mounts, renders every label in English, fetches the
	dictionary, and re-renders -- a flash of the wrong language on exactly the
	page where language matters most, plus a layout shift when the Kinyarwanda
	text turns out to be longer than the English it replaces.
	"""
	if lang == "en":
		return "null"

	try:
		full = get_all_translations(lang)
	except Exception:
		# A missing or malformed translation file must not take the portal
		# down: the SPA still has its own fetch as a fallback path.
		frappe.log_error(f"Portal translations unavailable for {lang}", "grm-portal")
		return "null"

	subset = {key: full[key] for key in _portal_strings() if key in full}
	# "</script>" anywhere in a translated value would otherwise end the block.
	return json.dumps(subset, ensure_ascii=False).replace("</", "<\\/")


def get_context(context):
	context.csrf_token = frappe.sessions.get_csrf_token()

	# Frappe's own resolution order -- ?_lang, then the preferred_language
	# cookie, then Accept-Language, then the user, then System Settings -- and
	# it validates against the enabled Language rows. The SPA writes that same
	# cookie when a citizen picks a language, so the server and the client
	# agree on the first paint instead of racing.
	lang = get_language()
	frappe.local.lang = lang

	context.portal_lang = lang
	context.portal_translations = _inline_translations(lang)
