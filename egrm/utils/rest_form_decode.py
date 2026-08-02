"""before_request hook: normalize form_dict for /api/resource/* requests.

Frappe's `frappe.api.v1.create_doc`/`update_doc` accept the request body
verbatim and pass it straight to `frappe.new_doc(doctype, **data)`. For
form-encoded POSTs that means every field arrives as a string. Two
problems follow:

1. Child-table fields (e.g. ``grm_project_link='[{"project":"RW-WB"}]'``)
   stay as strings and explode in `BaseDocument._init_child` with
   ``TypeError: 'str' object does not support item assignment``.
2. Numeric/Check fields stay as strings and break controller-level
   validators that run *before* DB-level typecasting (e.g. ``if
   self.level_order < 0:``).

This shim runs as a Frappe `before_request` hook and:

* JSON-decodes any scalar that looks like a JSON object/array.
* Coerces Int / Float / Check / Currency / Percent fields to their
  native Python type using DocType meta (best-effort; if meta is
  unavailable the value is left untouched).

It runs only for ``/api/resource/<DocType>`` POST/PUT/PATCH so RPC
bodies and asset requests are untouched.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, flt

_NUMERIC_FIELDTYPES = {"Int", "Long Int", "Check"}
_FLOAT_FIELDTYPES = {"Float", "Currency", "Percent"}


def _looks_like_json(value: object) -> bool:
	if not isinstance(value, str):
		return False
	s = value.strip()
	if not s:
		return False
	return s[0] in "[{"


def _doctype_from_path(path: str) -> str | None:
	# path: /api/resource/<DocType>[/<name>]
	parts = path.split("/")
	if len(parts) < 4 or parts[1] != "api" or parts[2] != "resource":
		return None
	from urllib.parse import unquote

	return unquote(parts[3])


def _coerce_typed_fields(doctype: str, form: dict) -> None:
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return
	for f in meta.fields:
		if f.fieldname not in form:
			continue
		value = form[f.fieldname]
		if not isinstance(value, str):
			continue
		if value == "":
			continue
		if f.fieldtype in _NUMERIC_FIELDTYPES:
			try:
				form[f.fieldname] = cint(value)
			except Exception:
				pass
		elif f.fieldtype in _FLOAT_FIELDTYPES:
			try:
				form[f.fieldname] = flt(value)
			except Exception:
				pass


def _rewrite_project_filter(doctype: str, form: dict) -> None:
	"""For doctypes whose `project` link lives in the `grm_project_link`
	child table (GRM Issue Status / Type / Category / Department /
	Citizen Group / Age Group), rewrite a top-level
	``[["project","=",X]]`` filter into the child-table filter syntax
	Frappe's reportview accepts: ``[["GRM Project Link","project","=",X]]``.

	Without this rewrite Frappe's `validate_fields` rejects the request
	with ``DataError: Field not permitted in query: project`` because
	the parent doctype has no direct `project` column. The AQE MP-8 /
	SEC / EC suites all hit this path via
	``/api/resource/GRM%20Issue%20Status?filters=[["project","=","RW-WB"], ...]``.
	"""
	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return
	# Only act when the doctype has NO direct `project` field but DOES
	# have a `grm_project_link` child table.
	if meta.get_field("project") is not None:
		return
	has_link = any(f.fieldname == "grm_project_link" and f.fieldtype == "Table" for f in meta.fields)
	if not has_link:
		return

	for key in ("filters", "or_filters"):
		raw = form.get(key)
		if not raw:
			continue
		# Filters arrive as JSON-string on GET /api/resource/<DocType>.
		if isinstance(raw, str):
			try:
				parsed = frappe.parse_json(raw)
			except Exception:
				continue
		else:
			parsed = raw
		if not isinstance(parsed, list):
			continue
		changed = False
		for i, clause in enumerate(parsed):
			# Frappe filter forms:
			#   [field, op, value]                 (3 elems)
			#   [parent_doctype, field, op, value] (4 elems)
			if isinstance(clause, list) and len(clause) == 3 and clause[0] == "project":
				parsed[i] = ["GRM Project Link", "project", clause[1], clause[2]]
				changed = True
		if changed:
			form[key] = parsed


def normalize_resource_form_dict() -> None:
	"""JSON-decode + numeric-coerce form_dict on /api/resource/* requests."""
	request = getattr(frappe.local, "request", None)
	if request is None:
		return
	path = request.path or ""
	if not path.startswith("/api/resource/"):
		return

	# GET — rewrite project filters for child-link-only doctypes.
	if request.method == "GET":
		doctype = _doctype_from_path(path)
		if doctype:
			form = frappe.local.form_dict
			if isinstance(form, dict):
				_rewrite_project_filter(doctype, form)
		return

	if request.method not in ("POST", "PUT", "PATCH"):
		return

	form = frappe.local.form_dict
	if not isinstance(form, dict):
		return

	# Step 1: JSON-decode obvious nested structures.
	for key, value in list(form.items()):
		if _looks_like_json(value):
			try:
				form[key] = frappe.parse_json(value)
			except Exception:
				continue

	# Step 2: numeric coercion driven by DocType meta.
	doctype = _doctype_from_path(path)
	if doctype:
		_coerce_typed_fields(doctype, form)
