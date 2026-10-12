"""Move translations between the shipped CSV files and the Translation doctype.

The app ships `egrm/translations/{lang}.csv`, which only a developer with a
deploy can change. Frappe merges the `Translation` doctype *over* those files
(frappe/translate.py: app files, then user translations), and anyone with the
Translator role can edit that doctype at `/app/translation`. Seeding the CSV
rows into it therefore turns every string in the product into something a
content person can correct the same afternoon, with no release.

The cost of that is drift: once a row exists in the doctype it wins, so a later
CSV fix for the same key is silently ignored. `write_back` is the other half of
the round trip -- it folds the doctype's values back into the CSV files so the
corrections can be committed and the two sources agree again.

    # make every shipped string editable in the UI
    bench --site <site> execute egrm.translation_sync.seed

    # fold UI corrections back into the CSVs, then commit them
    bench --site <site> execute egrm.translation_sync.write_back

    # move the corrections to another site
    bench --site <local>  execute egrm.translation_sync.dump
    # copy the file across, then
    bench --site <remote> execute egrm.translation_sync.load \
        --kwargs "{'path': '/tmp/egrm-translations.json'}"
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

import frappe
from frappe.utils import sanitize_html

logger = logging.getLogger(__name__)

# Languages the product ships a CSV for. "en" is the source language.
SHIPPED_LANGUAGES: tuple[str, ...] = ("fr", "rw")

DEFAULT_DUMP_PATH = "/tmp/egrm-translations.json"

# Commit every N writes. Large enough that the round trips are not the
# bottleneck, small enough that an interrupted run leaves most of its work.
_BATCH = 200


def _csv_path(lang: str) -> Path:
	return Path(frappe.get_app_path("egrm")) / "translations" / f"{lang}.csv"


def _read_csv(lang: str) -> dict[str, str]:
	"""The shipped file for `lang`, as {source_text: translated_text}."""
	path = _csv_path(lang)
	out: dict[str, str] = {}
	try:
		with path.open(newline="", encoding="utf-8") as fh:
			for row in csv.reader(fh):
				if len(row) >= 2 and row[0]:
					out[row[0]] = row[1]
	except FileNotFoundError:
		logger.error("No translation file for %s at %s", lang, path)
		raise
	return out


def _existing_rows(lang: str) -> dict[str, tuple[str, str]]:
	"""Translation rows for `lang` with no context, as {source: (name, text)}.

	Context-qualified rows are deliberately left out: they key on
	`source_text + ":" + context` in Frappe's merge and have no counterpart in
	the CSV files, so neither seeding nor write-back should touch them.
	"""
	rows = frappe.get_all(
		"Translation",
		filters={"language": lang, "context": ("in", ["", None])},
		fields=["name", "source_text", "translated_text"],
		limit_page_length=0,
	)
	return {r.source_text: (r.name, r.translated_text) for r in rows}


def _languages(lang: str | None) -> tuple[str, ...]:
	if not lang:
		return SHIPPED_LANGUAGES
	if lang not in SHIPPED_LANGUAGES:
		raise ValueError(f"{lang} is not a shipped language ({', '.join(SHIPPED_LANGUAGES)})")
	return (lang,)


def survives_doctype(translated: str) -> bool:
	"""Whether the Translation doctype can store `translated` unchanged.

	Translation.validate runs the value through sanitize_html, which strips
	anything shaped like a tag. Several of our strings carry angle-bracket
	placeholders -- "firstname.lastname@<domain>" -- and storing those loses
	the placeholder silently. A value that cannot survive the round trip has
	no business in the doctype: it stays CSV-only and a developer changes it.
	"""
	return sanitize_html(translated) == translated


def _upsert(lang: str, source: str, translated: str, existing: dict, overwrite: bool) -> str:
	"""Create or update one row. Returns "created", "updated", "kept" or "unsafe"."""
	if not survives_doctype(translated):
		logger.warning("%s: %r would be mangled by sanitize_html; left in the CSV", lang, source)
		return "unsafe"

	found = existing.get(source)
	if found is None:
		doc = frappe.get_doc(
			{
				"doctype": "Translation",
				"language": lang,
				"source_text": source,
				"translated_text": translated,
				"context": "",
			}
		)
		doc.insert(ignore_permissions=True)
		existing[source] = (doc.name, translated)
		return "created"

	name, current = found
	if current == translated or not overwrite:
		return "kept"
	doc = frappe.get_doc("Translation", name)
	doc.translated_text = translated
	doc.save(ignore_permissions=True)
	existing[source] = (name, translated)
	return "updated"


def seed(lang: str | None = None, overwrite: int = 0) -> dict[str, dict[str, int]]:
	"""Copy the shipped CSV rows into the Translation doctype.

	Idempotent. A source string that already has a row is left alone, because
	that row is almost certainly someone's correction -- `overwrite=1` is the
	deliberate opposite, for pushing a CSV fix over whatever is in the UI.

	Args:
		lang: One shipped language, or None for all of them.
		overwrite: 1 to replace existing rows whose text differs from the CSV.

	Returns:
		Per language, counts of created / updated / kept rows.
	"""
	overwrite = bool(int(overwrite))
	summary: dict[str, dict[str, int]] = {}

	for code in _languages(lang):
		if not frappe.db.exists("Language", code):
			logger.warning("Language %s has no Language record; skipping", code)
			continue

		shipped = _read_csv(code)
		existing = _existing_rows(code)
		counts = {"created": 0, "updated": 0, "kept": 0, "unsafe": 0}

		for i, (source, translated) in enumerate(shipped.items(), start=1):
			if not translated.strip():
				continue
			counts[_upsert(code, source, translated, existing, overwrite)] += 1
			if i % _BATCH == 0:
				frappe.db.commit()

		frappe.db.commit()
		summary[code] = counts
		logger.info("seed %s: %s", code, counts)
		print(
			f"{code}: {counts['created']} created, {counts['updated']} updated, "
			f"{counts['kept']} kept, {counts['unsafe']} left CSV-only"
		)

	frappe.clear_cache()
	return summary


def write_back(lang: str | None = None) -> dict[str, int]:
	"""Fold Translation-doctype values back into the shipped CSV files.

	This is what makes the doctype safe to edit: without it, every UI
	correction is a change that exists on one site and nowhere in the
	repository. Run it, then commit the CSV diff.

	Args:
		lang: One shipped language, or None for all of them.

	Returns:
		Per language, how many CSV rows changed.
	"""
	changed: dict[str, int] = {}

	for code in _languages(lang):
		shipped = _read_csv(code)
		rows = _existing_rows(code)

		n = 0
		for source, (_name, translated) in rows.items():
			if not translated.strip():
				continue
			current = shipped.get(source)
			if current == translated:
				continue
			# A row seeded before survives_doctype existed holds the sanitized
			# version of the CSV value. Folding that back would quietly delete
			# the placeholder from the file too, which is the one thing this
			# function must never do.
			if current is not None and sanitize_html(current) == translated:
				logger.warning(
					"%s: keeping CSV value for %r; the stored row is a sanitized copy", code, source
				)
				continue
			shipped[source] = translated
			n += 1

		path = _csv_path(code)
		with path.open("w", newline="", encoding="utf-8") as fh:
			writer = csv.writer(fh, lineterminator="\n")
			writer.writerows(sorted(shipped.items()))

		changed[code] = n
		logger.info("write_back %s: %d rows differ", code, n)
		print(f"{code}: {n} row(s) updated in {path}")

	return changed


def dump(path: str = DEFAULT_DUMP_PATH, lang: str | None = None) -> str:
	"""Write every Translation row to a JSON file, for moving between sites.

	Only the fields that define a translation are written. Row names are
	hashes and mean nothing on another site, so they are left out and `load`
	matches on (language, source_text, context) instead.

	Args:
		path: Where to write the file.
		lang: One language code, or None for every language present.

	Returns:
		The path written.
	"""
	filters = {"language": lang} if lang else {}
	rows = frappe.get_all(
		"Translation",
		filters=filters,
		fields=["language", "source_text", "translated_text", "context"],
		order_by="language asc, source_text asc",
		limit_page_length=0,
	)
	payload = [
		{
			"language": r.language,
			"source_text": r.source_text,
			"translated_text": r.translated_text,
			"context": r.context or "",
		}
		for r in rows
	]
	Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
	logger.info("dump: %d rows -> %s", len(payload), path)
	print(f"wrote {len(payload)} translation(s) to {path}")
	return path


def load(path: str = DEFAULT_DUMP_PATH, overwrite: int = 1) -> dict[str, int]:
	"""Read a `dump` file into this site's Translation doctype.

	Args:
		path: The JSON file produced by `dump`.
		overwrite: 1 (the default) to replace rows that differ. This is the
			opposite default from `seed` on purpose -- a dump is a deliberate
			export of corrections, so it is meant to win.

	Returns:
		Counts of created / updated / kept rows.
	"""
	overwrite = bool(int(overwrite))
	payload = json.loads(Path(path).read_text(encoding="utf-8"))
	counts = {"created": 0, "updated": 0, "kept": 0, "unsafe": 0, "skipped": 0}
	caches: dict[str, dict] = {}

	for i, row in enumerate(payload, start=1):
		code = row["language"]
		if not frappe.db.exists("Language", code):
			logger.warning("Language %s not on this site; skipping %r", code, row["source_text"])
			counts["skipped"] += 1
			continue
		if row.get("context"):
			# _existing_rows deliberately ignores context-qualified rows, so
			# upserting one here would create a duplicate on every run.
			counts["skipped"] += 1
			continue
		if code not in caches:
			caches[code] = _existing_rows(code)
		counts[_upsert(code, row["source_text"], row["translated_text"], caches[code], overwrite)] += 1
		if i % _BATCH == 0:
			frappe.db.commit()

	frappe.db.commit()
	frappe.clear_cache()
	logger.info("load: %s", counts)
	print(
		f"{counts['created']} created, {counts['updated']} updated, {counts['kept']} kept, {counts['skipped']} skipped"
	)
	return counts
