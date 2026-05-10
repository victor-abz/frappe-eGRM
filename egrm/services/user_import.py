"""Project-scoped user-import preprocessor for the Step 9 wizard.

This module is the server-side core of the Step 9 bulk-import flow. It is
called from the wizard RPC layer (``prepare_user_import``) and from the
forthcoming ``import-users`` CLI; it does NOT execute the import itself —
that is delegated to Frappe's built-in ``Data Import`` engine. Our job is
to make the user's CSV/XLSX *look like* a normal Data Import file by:

1. Resolving multiple admin-level columns (e.g. Province / District / Sector
   — names defined per project) into the single ``administrative_region``
   Link the doctype expects (``resolve_region``).
2. Auto-detecting a sane initial mapping from source headers to target
   doctype fields (``auto_detect_mapping``) — the user can override every
   guess in the UI.
3. Validating that mapping against the doctype's ``reqd: 1`` markers
   (``validate_mapping``) — never hard-coding "what must be in the CSV".
4. Materialising a staged CSV with one column per resolved target field,
   ready to be attached to a ``Data Import`` record
   (``materialize_staged_csv``).

Style mirrors ``admin_region_importer.py``: pure Python, structured
``dict`` returns, ``logger = logging.getLogger(__name__)``, errors
accumulated rather than raised (except for the documented
``auto_create=False`` path in ``resolve_region``).
"""

from __future__ import annotations

import csv
import logging
import os
import re
import time
from typing import Any

import frappe

logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 50

# Target tokens used in the mapping dict's ``target`` field. The "skip"
# sentinel is exposed to JS so the user can explicitly drop a column.
TARGET_SKIP = "(skip)"
TARGET_REGION = "administrative_region"


# ---------------------------------------------------------------------------
# A.1 — resolve_region
# ---------------------------------------------------------------------------

def resolve_region(
    row: dict,
    level_columns_ordered: list[tuple[str, str]],
    project: str,
    auto_create: bool = True,
    level_lookup: dict[str, str] | None = None,
) -> tuple[str | None, list[tuple[str, str, str]]]:
    """Resolve a list of admin-level cells into a single region id.

    Args:
        row: Original row dict (kept for API symmetry — not currently used,
            but downstream callers may want it for richer error messages).
        level_columns_ordered: ``[(level_type_name, source_value), ...]``
            ordered highest level first (Province → District → Sector …).
            ``level_type_name`` is the ``level_name`` of a
            ``GRM Administrative Level Type`` row scoped to ``project``.
        project: ``GRM Project.name``.
        auto_create: When ``True``, missing regions are inserted; when
            ``False``, a missing region raises ``frappe.ValidationError``.
        level_lookup: Optional pre-built ``{level_name: level_doc_name}``
            cache (one ``GRM Administrative Level Type`` row per entry).
            When provided, avoids a per-row × per-level DB roundtrip.
            When ``None``, falls back to per-row ``frappe.db.get_value``
            so direct callers don't need to know about the cache.

    Returns:
        ``(administrative_region_id, created)`` where ``created`` is the
        list of ``(level_type, value, new_region_id)`` tuples for any
        regions inserted along the way. Empty cells are skipped — region
        resolution stops at the last non-empty level (partial paths are
        legal).
    """
    del row  # currently unused; kept for forward compatibility.

    parent: str | None = None
    created: list[tuple[str, str, str]] = []

    for level_type, raw_value in level_columns_ordered:
        value = (raw_value or "").strip()
        if not value:
            # Empty cell ends resolution at the deepest non-empty ancestor.
            continue

        if level_lookup is not None:
            level_doc_name = level_lookup.get(level_type)
        else:
            level_doc_name = frappe.db.get_value(
                "GRM Administrative Level Type",
                {"project": project, "level_name": level_type},
                "name",
            )
        if not level_doc_name:
            # Level *types* are pre-seeded by Step 2; their absence is
            # always fatal — ``auto_create`` only governs region rows,
            # not level-type rows.
            raise frappe.ValidationError(
                f"Administrative level type not found: {level_type} (project={project}). "
                f"Run Step 2 first or seed the level type."
            )

        existing = frappe.db.exists(
            "GRM Administrative Region",
            {
                "project": project,
                "administrative_level": level_doc_name,
                "region_name": value,
                "parent_region": parent,
            },
        )
        if existing:
            parent = existing
            continue

        if not auto_create:
            raise frappe.ValidationError(
                f"Region not found: {level_type}={value} (project={project})"
            )

        new_doc = frappe.get_doc({
            "doctype": "GRM Administrative Region",
            "project": project,
            "administrative_level": level_doc_name,
            "region_name": value,
            "parent_region": parent,
        }).insert(ignore_permissions=False)
        created.append((level_type, value, new_doc.name))
        parent = new_doc.name

    return parent, created


# ---------------------------------------------------------------------------
# A.1 — auto_detect_mapping
# ---------------------------------------------------------------------------

def _normalize(label: str) -> str:
    """Lower, strip whitespace/underscores/non-alnum — for fuzzy matching."""
    return re.sub(r"[^a-z0-9]+", "", (label or "").lower())


def _user_field_lookup() -> dict[str, str]:
    """Map normalized User-doctype label/fieldname -> ``User.<fieldname>``.

    Excludes ``full_name`` — Frappe computes it from ``first_name`` +
    ``last_name`` at save time, so importing into it is a no-op. We also
    exclude it so a header literally named "Full Name" falls through to
    the name-split heuristic (which flags it for user confirmation).
    """
    out: dict[str, str] = {}
    for f in frappe.get_meta("User").fields:
        if not f.fieldname or f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
            continue
        if f.fieldname == "full_name":
            continue
        out[_normalize(f.fieldname)] = f"User.{f.fieldname}"
        if f.label:
            out[_normalize(f.label)] = f"User.{f.fieldname}"
    return out


def _assignment_field_lookup() -> dict[str, str]:
    """Map normalized Assignment-doctype label/fieldname -> ``Assignment.<fieldname>``.

    Excludes the ``administrative_region`` field — that target is reached
    via the dedicated TARGET_REGION sentinel (because it requires a
    sub-picker for *which* level type the source column represents).
    """
    out: dict[str, str] = {}
    for f in frappe.get_meta("GRM User Project Assignment").fields:
        if not f.fieldname or f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Table"):
            continue
        if f.fieldname == "administrative_region":
            continue
        out[_normalize(f.fieldname)] = f"Assignment.{f.fieldname}"
        if f.label:
            out[_normalize(f.label)] = f"Assignment.{f.fieldname}"
    return out


def _project_level_lookup(project_meta: dict) -> dict[str, str]:
    """Map normalized level-type name -> raw level-type name (for region sub-picker)."""
    out: dict[str, str] = {}
    for lvl in project_meta.get("project_levels") or []:
        name = (lvl.get("level_name") or "").strip()
        if not name:
            continue
        out[_normalize(name)] = name
    return out


def auto_detect_mapping(headers: list[str], project_meta: dict) -> dict:
    """Best-effort mapping ``{source_header: {target, level_type, ...}}``.

    Heuristic (matches plan §"Auto-detect heuristic" lines 111-115 in
    ``docs/superpowers/plans/2026-05-10-step9-users-redesign.md`` — that
    plan is the authoritative order):

    1. Header fuzzy match against ``User``-doctype field labels/fieldnames,
       then against ``GRM User Project Assignment`` field labels/fieldnames
       (case-insensitive, strip spaces/underscores).
    2. For unmatched columns, fuzzy match against
       ``GRM Administrative Level Type.level_name`` rows for the project —
       if matched, propose ``administrative_region`` + that level.
    3. Headers containing "name" → ``User.first_name`` / ``User.last_name``
       (split-needed when the header is just "name" or "full name" — we
       attach ``needs_split: True`` + a ``warning`` string so the UI can
       render a confirm-or-split prompt; user confirms in Phase E).

    Rationale for doctype-first ordering: plan order. The current
    User/Assignment doctypes have no field whose label matches a common
    admin-level name ("Province", "District", "Sector", "County", "Cell"),
    so today there is no collision. If a future project ever defines a
    level type whose name shadows a real doctype field label, the user
    can override the auto-detected target in the mapper UI.

    Unrecognized headers get ``target == TARGET_SKIP``.
    """
    user_fields = _user_field_lookup()
    asgn_fields = _assignment_field_lookup()
    level_lookup = _project_level_lookup(project_meta)

    mapping: dict[str, dict[str, Any]] = {}
    for header in headers:
        norm = _normalize(header)
        if not norm:
            mapping[header] = {"target": TARGET_SKIP, "level_type": None}
            continue

        # 1a. User field match (prefer User.email / User.first_name etc.)
        if norm in user_fields:
            mapping[header] = {"target": user_fields[norm], "level_type": None}
            continue

        # 1b. Assignment field match
        if norm in asgn_fields:
            mapping[header] = {"target": asgn_fields[norm], "level_type": None}
            continue

        # 2. Admin-level match for unmatched columns
        if norm in level_lookup:
            mapping[header] = {"target": TARGET_REGION, "level_type": level_lookup[norm]}
            continue

        # 3. "name"-bearing header heuristic. If the header is just "name"
        # or "full name", we can't tell first vs last — flag for the UI.
        if norm in {"fullname", "name"}:
            mapping[header] = {
                "target": "User.first_name",
                "level_type": None,
                "needs_split": True,
                "warning": (
                    "May contain full name — confirm this maps to first name only, "
                    "or split into two columns"
                ),
            }
            continue
        if "first" in norm and "name" in norm:
            mapping[header] = {"target": "User.first_name", "level_type": None}
            continue
        if "last" in norm and "name" in norm:
            mapping[header] = {"target": "User.last_name", "level_type": None}
            continue

        mapping[header] = {"target": TARGET_SKIP, "level_type": None}

    return mapping


# ---------------------------------------------------------------------------
# A.1 — validate_mapping
# ---------------------------------------------------------------------------

def _required_targets() -> list[tuple[str, str]]:
    """Return ``[(target_token, label), ...]`` for every must-have field.

    Required = the wizard's User minima (email/first_name/last_name) plus
    every ``GRM User Project Assignment`` field with ``reqd: 1`` *except*
    ``project`` (the wizard supplies that out-of-band).
    """
    required: list[tuple[str, str]] = []
    user_meta = frappe.get_meta("User")
    user_meta_by_name = {f.fieldname: f for f in user_meta.fields}
    for fname in ("email", "first_name", "last_name"):
        f = user_meta_by_name.get(fname)
        label = (f.label if f else fname) or fname
        required.append((f"User.{fname}", label))

    for f in frappe.get_meta("GRM User Project Assignment").fields:
        if not getattr(f, "reqd", 0):
            continue
        if f.fieldname == "project":
            continue
        label = f.label or f.fieldname
        required.append((f"Assignment.{f.fieldname}", label))
    return required


def validate_mapping(mapping: dict, project_meta: dict) -> dict:
    """Check that every required target is mapped exactly once.

    Returns:
        ``{"ok": bool, "missing_required": [label, ...],
            "errors": [str, ...], "warnings": [str, ...]}``
    """
    del project_meta  # required-set is doctype-driven, not project-meta-driven

    required = _required_targets()
    targets_in_use: list[tuple[str, str | None]] = []
    level_type_use: dict[str, list[str]] = {}

    for header, m in (mapping or {}).items():
        target = m.get("target")
        if not target or target == TARGET_SKIP:
            continue
        level_type = m.get("level_type")
        targets_in_use.append((target, level_type))
        if target == TARGET_REGION:
            if not level_type:
                # Caller surfaces this in `errors` so the UI can highlight
                # the offending row in the mapper table.
                continue
            level_type_use.setdefault(level_type, []).append(header)

    target_token_set = {t for t, _ in targets_in_use}

    missing_labels: list[str] = []
    for token, label in required:
        if token == TARGET_REGION:
            continue  # region is optional at the doctype level
        if token not in target_token_set:
            missing_labels.append(label)

    errors: list[str] = []
    warnings: list[str] = []

    # Multiple admin-level columns: enforce 'at most one column per level type'.
    for level_type, headers_using in level_type_use.items():
        if len(headers_using) > 1:
            errors.append(
                f"Multiple source columns mapped to admin level '{level_type}': "
                f"{', '.join(headers_using)}. Pick exactly one."
            )

    # Region target with no level_type sub-pick.
    for header, m in (mapping or {}).items():
        if m.get("target") == TARGET_REGION and not m.get("level_type"):
            errors.append(f"Column '{header}' is mapped to administrative_region but has no level type selected.")

    # Duplicate non-region target → warning (doctype will reject silently otherwise).
    seen_non_region: dict[str, str] = {}
    for header, m in (mapping or {}).items():
        target = m.get("target")
        if not target or target == TARGET_SKIP or target == TARGET_REGION:
            continue
        if target in seen_non_region:
            warnings.append(
                f"Both '{seen_non_region[target]}' and '{header}' map to {target}; "
                f"the second column will overwrite the first."
            )
        else:
            seen_non_region[target] = header

    ok = not missing_labels and not errors
    return {
        "ok": ok,
        "missing_required": missing_labels,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# A.1 — materialize_staged_csv
# ---------------------------------------------------------------------------

def _staged_dir() -> str:
    """Return the on-disk directory for staged user-import CSVs.

    Frappe's Data Import expects an attached file under ``private/files``
    (so it is reachable via ``/private/files/...``). We bucket all wizard
    user-imports into a single subdirectory for tidy lifecycle hooks.
    """
    base = frappe.get_site_path("private", "files", "grm_user_import")
    os.makedirs(base, exist_ok=True)
    return base


def _ordered_level_columns(mapping: dict) -> list[tuple[str, str]]:
    """Return ``[(level_type, source_header), ...]`` in source-column order.

    Source-column order implies hierarchy (left-to-right = highest-to-lowest)
    per plan line 116. The mapper UI lets the user re-order; this function
    just trusts whatever order the dict was given in (Python 3.7+ preserves
    insertion order).
    """
    ordered: list[tuple[str, str]] = []
    for header, m in mapping.items():
        if m.get("target") == TARGET_REGION and m.get("level_type"):
            ordered.append((m["level_type"], header))
    return ordered


def materialize_staged_csv(
    rows: list[list[str]],
    headers: list[str],
    mapping: dict,
    project: str,
    auto_create_regions: bool = True,
) -> dict:
    """Apply mapping + region resolution to every row, write a staged CSV.

    Output CSV has one column per *resolved target field* — i.e. the
    ``User.<x>`` and ``Assignment.<x>`` targets become bare ``<x>``
    columns suitable for Frappe's Data Import (which expects fieldnames
    or labels, not our ``Doctype.<fieldname>`` form). The single
    ``administrative_region`` column holds the resolved region id.

    Returns a structured dict with the staged path, counts, the list of
    regions that were (or would be) created, warnings, errors, and a
    preview of the first ``PREVIEW_LIMIT`` resolved-row dicts.
    """
    header_index = {h: i for i, h in enumerate(headers)}
    level_columns = _ordered_level_columns(mapping)

    # Build the output column list. Order: User fields (alpha), Assignment
    # fields (alpha), then administrative_region last (if any region cols).
    user_targets: list[str] = []
    asgn_targets: list[str] = []
    for _h, m in mapping.items():
        target = m.get("target")
        if not target or target == TARGET_SKIP or target == TARGET_REGION:
            continue
        if target.startswith("User."):
            fname = target.split(".", 1)[1]
            if fname not in user_targets:
                user_targets.append(fname)
        elif target.startswith("Assignment."):
            fname = target.split(".", 1)[1]
            if fname not in asgn_targets:
                asgn_targets.append(fname)

    out_headers = list(user_targets) + list(asgn_targets)
    if level_columns:
        out_headers.append("administrative_region")

    # ------------------------------------------------------------------
    # Caches built ONCE per call (vs per-row × per-target previously).
    # ------------------------------------------------------------------
    # 1) Level-name → level-doc-name. Saves N_rows × N_levels DB lookups.
    level_lookup: dict[str, str] = {
        row.level_name: row.name
        for row in frappe.get_all(
            "GRM Administrative Level Type",
            filters={"project": project},
            fields=["name", "level_name"],
        )
    }
    # 2) Target token → source header. ``_find_source_for`` semantics:
    #    on duplicate mappings the *last* declared header wins; replicate
    #    by overwriting on iteration. Region target is many-to-one
    #    (per-level-type), so it is handled separately via ``level_columns``
    #    and intentionally excluded here.
    target_to_source: dict[str, str] = {}
    for header, m in mapping.items():
        target = m.get("target")
        if not target or target == TARGET_SKIP or target == TARGET_REGION:
            continue
        target_to_source[target] = header

    preview: list[dict[str, Any]] = []
    rows_ready = 0
    rows_skipped = 0
    warnings: list[str] = []
    errors: list[str] = []
    regions_created_global: list[tuple[str, str, str]] = []
    regions_to_create_dryrun: set[tuple[str, str]] = set()

    out_path = os.path.join(_staged_dir(), f"users_{project}_{int(time.time())}.csv")
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(out_headers)

        for row_num, raw_row in enumerate(rows, start=2):
            row_dict = {h: (raw_row[header_index[h]] if header_index[h] < len(raw_row) else "")
                        for h in headers if h in header_index}

            level_cells: list[tuple[str, str]] = []
            for level_type, src_header in level_columns:
                level_cells.append((level_type, (row_dict.get(src_header) or "").strip()))

            try:
                region_id = None
                if level_cells and any(v for _, v in level_cells):
                    if auto_create_regions:
                        region_id, created_here = resolve_region(
                            row_dict, level_cells, project, auto_create=True,
                            level_lookup=level_lookup,
                        )
                        regions_created_global.extend(created_here)
                    else:
                        # Dry-run: don't write, but compute what *would* be needed.
                        region_id = _resolve_region_dryrun(
                            level_cells, project, regions_to_create_dryrun,
                            level_lookup=level_lookup,
                        )
            except frappe.ValidationError as exc:
                errors.append(f"Row {row_num}: {exc}")
                rows_skipped += 1
                continue

            # Locked dry-run contract: if auto_create_regions=False AND the
            # row had non-empty admin-level cells but resolved to no region,
            # do NOT write a NULL-region row to the staged CSV (Frappe Data
            # Import would otherwise silently insert assignments with
            # administrative_region=NULL). Skip the row, record the first
            # missing level for the error message.
            if (
                not auto_create_regions
                and level_cells
                and any(v for _, v in level_cells)
                and region_id is None
            ):
                first_missing_level, first_missing_value = next(
                    (lt, v) for lt, v in level_cells if v
                )
                errors.append(
                    f"Row {row_num}: region {first_missing_level}={first_missing_value!r} "
                    f"does not exist (auto_create=False)"
                )
                rows_skipped += 1
                continue

            out_row: list[str] = []
            resolved: dict[str, Any] = {}

            for fname in user_targets:
                src_header = target_to_source.get(f"User.{fname}")
                val = (row_dict.get(src_header) or "").strip() if src_header else ""
                out_row.append(val)
                resolved[fname] = val
            for fname in asgn_targets:
                src_header = target_to_source.get(f"Assignment.{fname}")
                val = (row_dict.get(src_header) or "").strip() if src_header else ""
                out_row.append(val)
                resolved[fname] = val
            if level_columns:
                out_row.append(region_id or "")
                resolved["administrative_region"] = region_id or ""

            writer.writerow(out_row)
            rows_ready += 1
            if len(preview) < PREVIEW_LIMIT:
                preview.append(resolved)

    regions_to_create = (
        [(lt, val, new_id) for lt, val, new_id in regions_created_global]
        if auto_create_regions
        else [(lt, val) for lt, val in sorted(regions_to_create_dryrun)]
    )

    return {
        "staged_path": out_path,
        "rows_total": len(rows),
        "rows_ready": rows_ready,
        "rows_skipped": rows_skipped,
        "regions_to_create": regions_to_create,
        "warnings": warnings,
        "errors": errors,
        "preview": preview,
    }


def _find_source_for(mapping: dict, target: str) -> str | None:
    """Reverse-lookup: which source header maps to ``target``?

    On duplicate mappings (which ``validate_mapping`` flags as a warning),
    the *last* declared header wins — same as Python dict iteration order
    when the user's mapper UI rewrites the dict in place.
    """
    chosen: str | None = None
    for header, m in mapping.items():
        if m.get("target") == target:
            chosen = header
    return chosen


def _resolve_region_dryrun(
    level_cells: list[tuple[str, str]],
    project: str,
    accumulator: set[tuple[str, str]],
    level_lookup: dict[str, str] | None = None,
) -> str | None:
    """Walk the hierarchy without inserting; record any missing levels.

    Mirrors ``resolve_region`` but never writes. Records each missing
    ``(level_type, value)`` pair into ``accumulator`` so the caller can
    surface them as the ``regions_to_create`` preview list.

    ``level_lookup`` is the same optional cache as ``resolve_region``;
    callers building it once across many rows pass it here too.
    """
    parent: str | None = None
    for level_type, raw_value in level_cells:
        value = (raw_value or "").strip()
        if not value:
            continue
        if level_lookup is not None:
            level_doc_name = level_lookup.get(level_type)
        else:
            level_doc_name = frappe.db.get_value(
                "GRM Administrative Level Type",
                {"project": project, "level_name": level_type},
                "name",
            )
        if not level_doc_name:
            accumulator.add((level_type, value))
            return None
        existing = frappe.db.exists(
            "GRM Administrative Region",
            {
                "project": project,
                "administrative_level": level_doc_name,
                "region_name": value,
                "parent_region": parent,
            },
        )
        if existing:
            parent = existing
            continue
        accumulator.add((level_type, value))
        # Once a level is missing, any deeper level can't be looked up; stop.
        return None
    return parent
