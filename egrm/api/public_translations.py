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
