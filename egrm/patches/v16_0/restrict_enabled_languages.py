# Copyright (c) 2026, eGRM and contributors
# For license information, please see license.txt
"""Enable only English, French and Kinyarwanda; disable every other Language.

Frappe ships ~82 ``Language`` rows and enables a scattered subset of them
(Arabic, Bosnian, Thai, Chinese …) that eGRM has no translations for, while
``rw`` — the language most of the country actually files grievances in —
shipped disabled. The desk language picker and the ``User.language`` link
field both filter on ``enabled = 1``, so Kinyarwanda never appeared and a
pile of irrelevant locales did.

eGRM ships translations for ``fr`` and ``rw`` (``egrm/translations/``); ``en``
is the source language. Those three are the supported set.

Users already sitting on a language this patch disables keep their setting —
it still resolves for translation lookups — but they can no longer pick it
again from the dropdown. Their names are printed so the choice is visible
rather than silent.

Idempotent: re-running finds the flags already correct and writes nothing.
"""

import frappe

SUPPORTED_LANGUAGES = ("en", "fr", "rw")


def execute():  # type: ignore[no-untyped-def]
    rows = frappe.get_all("Language", fields=["name", "enabled"])

    enabled_count = 0
    disabled_count = 0

    for row in rows:
        should_be_enabled = 1 if row.name in SUPPORTED_LANGUAGES else 0
        if int(row.enabled or 0) == should_be_enabled:
            continue
        frappe.db.set_value(
            "Language", row.name, "enabled", should_be_enabled, update_modified=False
        )
        if should_be_enabled:
            enabled_count += 1
        else:
            disabled_count += 1

    missing = [
        code
        for code in SUPPORTED_LANGUAGES
        if not frappe.db.exists("Language", code)
    ]
    if missing:
        # Should not happen on a stock Frappe install, but a missing row would
        # silently drop the language from the picker — surface it loudly.
        print(
            "restrict_enabled_languages: WARNING — expected Language rows "
            f"absent: {missing}"
        )

    # Anyone parked on a locale we just switched off keeps working, but the
    # operator should know who they are.
    stranded = frappe.get_all(
        "User",
        filters={
            "language": ["not in", list(SUPPORTED_LANGUAGES)],
            "enabled": 1,
        },
        fields=["name", "language"],
    )
    stranded = [u for u in stranded if u.language]

    if enabled_count or disabled_count:
        frappe.clear_cache()
        frappe.db.commit()

    print(
        f"restrict_enabled_languages: enabled {enabled_count}, "
        f"disabled {disabled_count}; supported set = {list(SUPPORTED_LANGUAGES)}"
    )
    if stranded:
        print(
            f"restrict_enabled_languages: {len(stranded)} enabled user(s) still "
            f"set to a now-disabled language: "
            f"{[(u.name, u.language) for u in stranded[:20]]}"
        )
