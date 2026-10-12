#!/usr/bin/env python3
"""Extract every user-visible string in the grm-portal SPA.

The portal uses ~200 of the ~1,470 keys in a translation file. Knowing which
200 lets the server inline just those into the page (see
``egrm/www/grm-portal.py``), which is what removes both the 82 KB dictionary
fetch and the flash of English between first paint and the dictionary
arriving.

Run with ``--check`` in CI: it fails when the committed manifest is stale, or
when a shipped language is missing a translation for a key the UI renders.
Without that check the gap is invisible -- a missing key renders as its
English source, which looks like a deliberate choice rather than a hole.

    python3 scripts/extract_portal_strings.py          # rewrite the manifest
    python3 scripts/extract_portal_strings.py --check  # verify, exit 1 if stale
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
SRC = APP_ROOT / "grm-portal" / "src"
MANIFEST = APP_ROOT / "egrm" / "portal_strings.json"
TRANSLATIONS = APP_ROOT / "egrm" / "translations"

# Languages the portal offers. Matches FALLBACK_LANGUAGES in
# grm-portal/src/hooks/useTranslate.ts and the rows
# egrm/patches/v16_0/restrict_enabled_languages.py enables. "en" is the
# source language and has no file.
SHIPPED_LANGUAGES = ("fr", "rw")

# __("literal") / __("literal", [...]) -- double-quoted, escapes allowed.
CALL = re.compile(r'__\(\s*"((?:[^"\\]|\\.)*)"')

# Tables of UI copy hold their labels as bare string constants that are passed
# through __() at the point of render, so the call-site regex cannot see them:
# the Navbar's links, HomePage's process steps, DashboardPage's date ranges,
# the router's page titles. This used to be anchored to a whole line and
# applied to HomePage.tsx alone, which missed every one-line object literal
# (`{ to: "/x", label: "Home", icon: Home }`) and every other file -- so a new
# nav label could ship untranslated with --check still passing.
FIELD = re.compile(r'\b(?:title|description|cta|label):\s*"((?:[^"\\]|\\.)*)"')

# Caught by FIELD but not translatable: a proper noun rendered as-is, never
# passed through __(). Demanding a Kinyarwanda row for "WhatsApp" would be
# asking for a translation that should not exist.
PROPER_NOUNS = {"WhatsApp"}


def extract() -> list[str]:
	keys: set[str] = set()
	for path in sorted([*SRC.rglob("*.ts"), *SRC.rglob("*.tsx")]):
		text = path.read_text(encoding="utf-8")
		keys.update(CALL.findall(text))
		keys.update(FIELD.findall(text))
	# Empty strings come from form state initialisers that happen to use these
	# field names; there is nothing to translate.
	return sorted(k for k in keys if k.strip() and k not in PROPER_NOUNS)


def load_translations(lang: str) -> dict[str, str]:
	path = TRANSLATIONS / f"{lang}.csv"
	out: dict[str, str] = {}
	with path.open(newline="", encoding="utf-8") as fh:
		for row in csv.reader(fh):
			if len(row) >= 2 and row[0]:
				out[row[0]] = row[1]
	return out


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--check", action="store_true", help="verify instead of rewrite")
	args = parser.parse_args()

	keys = extract()

	if not args.check:
		MANIFEST.write_text(json.dumps(keys, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
		print(f"wrote {MANIFEST.relative_to(APP_ROOT)} ({len(keys)} strings)")
		return 0

	failures: list[str] = []

	committed = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
	if committed != keys:
		added = sorted(set(keys) - set(committed))
		removed = sorted(set(committed) - set(keys))
		failures.append(
			f"{MANIFEST.relative_to(APP_ROOT)} is stale "
			f"(+{len(added)} / -{len(removed)}). Run: python3 scripts/extract_portal_strings.py"
		)
		for k in added[:10]:
			failures.append(f"    + {k}")
		for k in removed[:10]:
			failures.append(f"    - {k}")

	for lang in SHIPPED_LANGUAGES:
		have = load_translations(lang)
		missing = [k for k in keys if not have.get(k, "").strip()]
		if missing:
			failures.append(f"{lang}.csv is missing {len(missing)} of {len(keys)} portal strings:")
			for k in missing[:20]:
				failures.append(f"    {k}")
			if len(missing) > 20:
				failures.append(f"    ... and {len(missing) - 20} more")

	if failures:
		print("\n".join(failures), file=sys.stderr)
		return 1

	print(f"portal strings OK: {len(keys)} strings, all translated in {', '.join(SHIPPED_LANGUAGES)}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
