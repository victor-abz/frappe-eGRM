"""Align the RDAP issue taxonomy with the signed customization questionnaire.

Source of truth: "RISA - eGRM Customization Questionnairre.docx".

The categories and issue types that were seeded before this script were not
drawn from that document -- "Complaint", "Service Issue", "SMS", "In Person"
and "Written" appear nowhere in it, while six of the seven categories the
project actually signed off on were missing. This restores both lists to what
the questionnaire says, and nothing else: every value below cites the section
it comes from, so a reviewer can check it against the document line by line.

Two tables, two different sections:

  * GRM Issue Category  <- section 5 ("Types of Issues"), with the routing
    level from section 6 ("Typology and Routing of Issues"). Section 6 routes
    by category name to an administrative level, and GRM Issue Category is the
    only doctype carrying `administrative_level`, so the section 5 list belongs
    here rather than on GRM Issue Type.

  * GRM Issue Type      <- section 2 ("Uptake Information") and section 4,
    which between them enumerate how feedback is expected to arrive. This
    table is the intake channel, not a second typology.

Safety: a category or type that still has issues attached is never deleted.
It is reported instead, because dropping it would orphan real citizen reports
on a production site. Remapping such rows requires an explicit entry in
the `remap` argument of run(), so that moving live data is always a deliberate,
reviewable act rather than a default.

Usage (dry run prints the diff and changes nothing):

    bench --site <site> execute egrm.scripts.seed_rdap_taxonomy.run
    bench --site <site> execute egrm.scripts.seed_rdap_taxonomy.run \
        --kwargs "{'apply': True}"
"""

from __future__ import annotations

import frappe

PROJECT = "RDAP"

# --- Section 5 + 6 -----------------------------------------------------------
# (category_name, app label, abbreviation, routing level name per section 6)
#
# Section 5 marks all seven "Include in GRM? = Y". The "Name of the Category on
# the App Interface" column is reproduced verbatim in `label`, including its
# inconsistent capitalisation ("Bursary related Complaint"), because that is
# what the project asked citizens to be shown.
#
# Section 6 assigns every category to ADM0 except Digital Literacy, which goes
# to ADM 1. Section 3 names ADM0 = PIU and ADM1 = Province.
CATEGORIES: list[tuple[str, str, str, str]] = [
	("Others", "Others", "OTH", "PIU"),
	("Appreciation", "Appreciation", "APP", "PIU"),
	("Question", "Question", "QUE", "PIU"),
	("Suggestion or Feedback", "Suggestion or Feedback", "SUG", "PIU"),
	("Bursary Related Complaint", "Bursary related Complaint", "BUR", "PIU"),
	("Grant Related Complaint", "Grant related complaint", "GRA", "PIU"),
	("Digital Literacy", "Digital Literacy", "DLT", "Province"),
]

# --- Section 2 + 4 -----------------------------------------------------------
# Each channel cites the line that puts it in the document. Anything not
# traceable to a line is not seeded -- that is how "SMS" got in last time.
ISSUE_TYPES: list[tuple[str, str]] = [
	("Mobile App", "s2: uptake 'directly from citizens using a smartphone'"),
	("Web Form", "s4: 'through the app or the web dashboard'"),
	("Phone Call", "s2: 'call center or support number ... Yes (0783349090, 0788569697)'"),
	("Email", "s2: 'Emails'"),
	("Verbal", "s2: 'Verbal comments (face to face discussion)'"),
]

# Renames applied before matching, so a category keeps its id -- and therefore
# its attached issues -- instead of being deleted and recreated under a new one.
RENAME_CATEGORIES = {"Other": "Others"}

# Categories that are not in the questionnaire but still carry issues are never
# touched by default. Moving them is a per-site decision -- on a production site
# "Complaint" may hold real citizen grievances that must not be silently
# relabelled -- so the mapping is passed to run() by the operator rather than
# baked in here where it would apply everywhere.

# Section 11 does not set confidentiality per category; it asks for the
# citizen's Name to be hidden, which is a field-level control elsewhere. The
# field is mandatory, so new rows take the open value and the gap is reported.
DEFAULT_CONFIDENTIALITY = "Public"

# Section 6 leaves "Assigned to Specific Roles (optional)" blank for all seven
# categories -- the routing it specifies is by administrative level, which is
# what `administrative_level` above carries. But GRM Issue Category validates
# that a role is set and rejects department-based routing outright, so a role
# is required to save the row at all. This is the role every existing RDAP
# category already routes to; it is an implementation default, not a value
# taken from the questionnaire.
ROUTING_ROLE_NAME = "Project Administrator"


def _level_id(level_name: str) -> str | None:
	return frappe.db.get_value(
		"GRM Administrative Level Type",
		{"project": PROJECT, "level_name": level_name},
		"name",
	)


def _has_project_link(doc, project: str) -> bool:
	return any(r.project == project for r in doc.get("grm_project_link") or [])


def run(apply: bool = False, remap: dict[str, str] | None = None) -> dict:
	remap = remap or {}
	changes: list[str] = []
	blocked: list[str] = []

	routing_role = frappe.db.get_value(
		"GRM Project Role", {"project": PROJECT, "role_name": ROUTING_ROLE_NAME}, "name"
	)
	if not routing_role:
		return {
			"applied": False,
			"error": f"GRM Project Role {ROUTING_ROLE_NAME!r} not found for {PROJECT}; "
			"a category cannot be saved without a routing role.",
		}

	level_ids = {name: _level_id(name) for name in {c[3] for c in CATEGORIES}}
	missing_levels = [n for n, v in level_ids.items() if not v]
	if missing_levels:
		return {
			"applied": False,
			"error": f"administrative level(s) not found for {PROJECT}: {missing_levels}. "
			"Run scripts/seed_rdap_structure.py first.",
		}

	# ---- categories ---------------------------------------------------------
	# `by_name` is the planned state, not the stored one. A dry run that looked
	# category names up in the database would miss the renames below and report
	# a CREATE and a DELETE for a row that apply mode merely renames -- a diff
	# that does not match what applying it would actually do.
	by_name: dict[str, str] = {
		r.category_name: r.name
		for r in frappe.get_all(
			"GRM Issue Category", filters={"project": PROJECT}, fields=["name", "category_name"]
		)
	}

	for old, new in RENAME_CATEGORIES.items():
		row = by_name.get(old)
		if row and new not in by_name:
			changes.append(f"RENAME category {old!r} -> {new!r} [{row}]")
			by_name[new] = by_name.pop(old)
			if apply:
				doc = frappe.get_doc("GRM Issue Category", row)
				doc.category_name = new
				doc.label = new
				doc.save(ignore_permissions=True)

	wanted_cats = {c[0] for c in CATEGORIES}
	for category_name, label, abbr, level_name in CATEGORIES:
		existing = by_name.get(category_name)
		target_level = level_ids[level_name]
		if existing:
			doc = frappe.get_doc("GRM Issue Category", existing)
			dirty = []
			if doc.label != label:
				dirty.append(f"label {doc.label!r}->{label!r}")
				doc.label = label
			if doc.abbreviation != abbr:
				dirty.append(f"abbr {doc.abbreviation!r}->{abbr!r}")
				doc.abbreviation = abbr
			if doc.administrative_level != target_level:
				was = frappe.db.get_value(
					"GRM Administrative Level Type", doc.administrative_level, "level_name"
				)
				dirty.append(f"level {was!r}->{level_name!r}")
				doc.administrative_level = target_level
			if doc.routing_target_type != "Role":
				dirty.append(f"routing {doc.routing_target_type!r}->'Role'")
				doc.routing_target_type = "Role"
			if not doc.assigned_role:
				dirty.append(f"role -> {ROUTING_ROLE_NAME!r}")
				doc.assigned_role = routing_role
			if not _has_project_link(doc, PROJECT):
				dirty.append("add project link")
				doc.append("grm_project_link", {"project": PROJECT})
			if dirty:
				changes.append(f"UPDATE category {category_name!r}: {', '.join(dirty)}")
				if apply:
					doc.save(ignore_permissions=True)
		else:
			changes.append(f"CREATE category {category_name!r} level={level_name}")
			if apply:
				doc = frappe.new_doc("GRM Issue Category")
				doc.project = PROJECT
				doc.category_name = category_name
				doc.label = label
				doc.abbreviation = abbr
				doc.administrative_level = target_level
				doc.confidentiality_level = DEFAULT_CONFIDENTIALITY
				doc.redirection_protocol = 0
				doc.routing_target_type = "Role"
				doc.assigned_role = routing_role
				doc.append("grm_project_link", {"project": PROJECT})
				doc.insert(ignore_permissions=True)
				by_name[category_name] = doc.name

	# ---- categories not in the questionnaire --------------------------------
	for category_name, docname in sorted(by_name.items()):
		row = frappe._dict(name=docname, category_name=category_name)
		if row.category_name in wanted_cats:
			continue
		count = frappe.db.count("GRM Issue", {"category": row.name})
		if count == 0:
			changes.append(f"DELETE category {row.category_name!r} (no issues)")
			if apply:
				frappe.delete_doc("GRM Issue Category", row.name, ignore_permissions=True, force=True)
		elif row.category_name in remap:
			target_name = remap[row.category_name]
			target = by_name.get(target_name)
			if not target:
				blocked.append(f"remap target {target_name!r} does not exist")
				continue
			changes.append(f"REMAP {count} issue(s) {row.category_name!r} -> {target_name!r}, then delete")
			if apply:
				frappe.db.set_value(
					"GRM Issue", {"category": row.name}, "category", target, update_modified=False
				)
				frappe.delete_doc("GRM Issue Category", row.name, ignore_permissions=True, force=True)
		else:
			blocked.append(
				f"category {row.category_name!r} is not in the questionnaire but holds "
				f"{count} issue(s); pass remap={{{row.category_name!r}: '<target>'}} to move them"
			)

	# ---- issue types --------------------------------------------------------
	wanted_types = {t[0] for t in ISSUE_TYPES}
	for type_name, _source in ISSUE_TYPES:
		existing = frappe.db.get_value("GRM Issue Type", {"project": PROJECT, "type_name": type_name}, "name")
		if existing:
			doc = frappe.get_doc("GRM Issue Type", existing)
			if not _has_project_link(doc, PROJECT):
				changes.append(f"UPDATE type {type_name!r}: add project link")
				if apply:
					doc.append("grm_project_link", {"project": PROJECT})
					doc.save(ignore_permissions=True)
		else:
			changes.append(f"CREATE type {type_name!r}")
			if apply:
				doc = frappe.new_doc("GRM Issue Type")
				doc.project = PROJECT
				doc.type_name = type_name
				doc.append("grm_project_link", {"project": PROJECT})
				doc.insert(ignore_permissions=True)

	for row in frappe.get_all("GRM Issue Type", filters={"project": PROJECT}, fields=["name", "type_name"]):
		if row.type_name in wanted_types:
			continue
		count = frappe.db.count("GRM Issue", {"issue_type": row.name})
		if count == 0:
			changes.append(f"DELETE type {row.type_name!r} (no issues)")
			if apply:
				frappe.delete_doc("GRM Issue Type", row.name, ignore_permissions=True, force=True)
		else:
			blocked.append(
				f"issue type {row.type_name!r} is not in the questionnaire but holds "
				f"{count} issue(s); move them before it can be removed"
			)

	if apply:
		frappe.db.commit()

	return {
		"applied": apply,
		"change_count": len(changes),
		"changes": changes,
		"blocked": blocked,
	}
