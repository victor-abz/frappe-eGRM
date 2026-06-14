"""
eGRM API - Public Translations
-------------------------------
Guest-accessible endpoint that returns translations for a given language code.
Frappe's built-in get_app_translations ignores the _lang parameter and reads
the user's DB language setting, which doesn't work for a public SPA where
guests pick their language from a dropdown.
"""

import frappe
from frappe.translate import get_all_translations


@frappe.whitelist(allow_guest=True)
def get_translations(lang=None):
	"""Return merged translation dict for the requested language.

	Args:
	    lang: Language code (e.g. "fr", "rw", "sw"). Defaults to system language.

	Returns:
	    dict: {source_string: translated_string, ...}
	"""
	if not lang or lang == "en":
		return {}

	return get_all_translations(lang)


@frappe.whitelist(allow_guest=True)
def get_preferred_language(project=None):
	"""Return the language the SPA should default to.

	Resolution order:
	1. Logged-in user's ``User.language`` (when not Guest).
	2. The supplied ``project``'s ``default_language``.
	3. System Settings' ``language``.
	4. Empty string (caller falls back to its hardcoded default).

	The cookie set by the SPA's language dropdown takes precedence client-side;
	this endpoint only fills in the initial value when no cookie is set yet.
	"""
	user = frappe.session.user
	if user and user != "Guest":
		user_lang = frappe.db.get_value("User", user, "language")
		if user_lang:
			return {"language": user_lang, "source": "user"}

	if project:
		proj_lang = frappe.db.get_value("GRM Project", project, "default_language")
		if proj_lang:
			return {"language": proj_lang, "source": "project"}

	system_lang = frappe.db.get_single_value("System Settings", "language")
	if system_lang:
		return {"language": system_lang, "source": "system"}

	return {"language": "", "source": "none"}
