"""Project-scoped administrative region bulk-importer.

This module is the single source of truth for hierarchical admin-region
ingestion. The CLI command (``import-admin-regions``) and the wizard
RPC endpoints (``parse_admin_regions_csv`` / ``bulk_insert_admin_regions``)
both call ``HierarchicalAdminProcessor``.

The importer:
1. Validates the CSV header (level columns + optional Latitude/Longitude).
2. Auto-creates the highest-level GRM Administrative Level Type
   (level_order=0) plus any missing inner levels (level_order=1..N).
3. Inserts GRM Administrative Region rows with parent_region links and
   computes the materialized ``path`` field.
4. Returns a structured report (created/updated counts, errors).
"""

import csv
import io
import logging
from typing import Iterable

import frappe

logger = logging.getLogger(__name__)

MAX_PREVIEW_ROWS = 50


class HierarchicalAdminProcessor:
    """Processes administrative regions using hierarchical approach with materialized paths."""

    def __init__(self, project_code: str, highest_level: str, log: logging.Logger | None = None):
        self.project_code = project_code
        self.highest_level = (highest_level or "Country").strip() or "Country"
        self.log = log or logger
        self.hierarchy_tree: dict = {}
        self.level_names: list[str] = []
        self.created_levels: dict[str, int] = {}
        self.created_regions: dict[str, str] = {}
        self.path_to_region: dict[str, str] = {}
        self.total_created: int = 0
        self.total_updated: int = 0
        self.errors: list[str] = []

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------
    def process_csv(self, csv_file_path: str) -> bool:
        """Legacy file-path entry point used by the CLI."""
        try:
            with open(csv_file_path, "r", encoding="utf-8") as fh:
                csv_text = fh.read()
        except OSError as exc:
            self._record_error(f"Cannot read CSV file {csv_file_path}: {exc}")
            return False
        return self._process_text(csv_text)

    def run(self, csv_text: str) -> dict:
        """Service-mode entry: parse + insert. Returns counts and errors."""
        ok = self._process_text(csv_text)
        return {
            "ok": ok,
            "created": self.total_created,
            "updated": self.total_updated,
            "errors": list(self.errors),
            "highest_level": self.highest_level,
            "level_columns": list(self.level_names),
        }

    def parse_only(self, csv_text: str) -> dict:
        """Validate CSV without writing. Returns preview rows (dict-shaped, keyed by header) and errors."""
        rows, headers, parse_errors = self._read_csv_rows(csv_text)
        validation_errors = self._validate_rows(rows, headers)
        preview = [
            {headers[i]: cell for i, cell in enumerate(row)}
            for row in rows[:MAX_PREVIEW_ROWS]
        ]
        return {
            "preview": preview,
            "total_rows": len(rows),
            "errors": parse_errors + validation_errors,
            "highest_level": self.highest_level,
            "level_columns": headers,
        }

    # ------------------------------------------------------------------
    # Core flow
    # ------------------------------------------------------------------
    def _process_text(self, csv_text: str) -> bool:
        try:
            rows, headers, parse_errors = self._read_csv_rows(csv_text)
            if parse_errors:
                self.errors.extend(parse_errors)
                return False
            if not rows:
                self._record_error("CSV file is empty or has no data rows")
                return False

            self.level_names = headers
            for row in rows:
                self._add_to_hierarchy_tree(row)

            if not self._create_administrative_levels():
                return False
            if not self._create_highest_level_region():
                return False
            if not self._create_hierarchical_regions():
                return False
            self.log.info("Successfully completed hierarchical processing")
            return True
        except Exception as exc:
            self._record_error(f"Error in process_csv: {exc}")
            return False

    # ------------------------------------------------------------------
    # CSV parsing
    # ------------------------------------------------------------------
    def _read_csv_rows(self, csv_text: str) -> tuple[list[list[str]], list[str], list[str]]:
        """Return (rows, headers, errors). Rows are list-of-cell-strings, validated for length."""
        errors: list[str] = []
        reader = csv.reader(io.StringIO(csv_text))
        try:
            headers_raw = next(reader)
        except StopIteration:
            return [], [], ["CSV file is empty or has no headers"]
        headers = [h.strip() for h in headers_raw if h is not None]
        if not headers:
            return [], [], ["CSV file must have at least one column"]

        rows: list[list[str]] = []
        for row_num, row in enumerate(reader, start=2):
            if not row or all((cell or "").strip() == "" for cell in row):
                continue
            if len(row) != len(headers):
                errors.append(
                    f"Row {row_num} has {len(row)} columns, expected {len(headers)}. Skipping."
                )
                continue
            clean = [(cell or "").strip() for cell in row]
            rows.append(clean)
        return rows, headers, errors

    def _validate_rows(self, rows: Iterable[list[str]], headers: list[str]) -> list[str]:
        """Validate already-shape-checked rows. Returns a list of human-readable errors."""
        errors: list[str] = []
        for row_num, row in enumerate(rows, start=2):
            for i, value in enumerate(row):
                if not value:
                    errors.append(
                        f"Row {row_num}: Empty value at level '{headers[i] if i < len(headers) else i}'."
                    )
                    break
                if len(value) > 140:
                    errors.append(
                        f"Row {row_num}: Value '{value[:50]}...' is too long (>140 chars)."
                    )
                    break
        return errors

    def _detect_level_columns(self) -> list[str]:
        """Compatibility helper used by the wizard preview pane."""
        return list(self.level_names)

    def _add_to_hierarchy_tree(self, row: list[str]) -> None:
        current_level = self.hierarchy_tree
        path_parts: list[str] = []
        for i, value in enumerate(row):
            path_parts.append(value)
            current_path = ":".join(path_parts)
            if value not in current_level:
                current_level[value] = {
                    "_children": {},
                    "_path": current_path,
                    "_level_index": i,
                    "_full_path_parts": path_parts.copy(),
                }
            current_level = current_level[value]["_children"]

    # ------------------------------------------------------------------
    # Level / region creation
    # ------------------------------------------------------------------
    def _create_administrative_levels(self) -> bool:
        try:
            self.log.info("Creating administrative levels...")
            highest_level_name = self.highest_level
            existing_highest = frappe.db.exists(
                "GRM Administrative Level Type",
                {"level_name": highest_level_name, "project": self.project_code},
            )
            if not existing_highest:
                doc = frappe.new_doc("GRM Administrative Level Type")
                doc.level_name = highest_level_name
                doc.level_order = 0
                doc.project = self.project_code
                doc.insert()
                self.log.info(f"Created highest administrative level: {highest_level_name}")
                self.total_created += 1
            self.created_levels[highest_level_name] = 0

            for i, level_name in enumerate(self.level_names):
                level_order = i + 1
                existing = frappe.db.exists(
                    "GRM Administrative Level Type",
                    {"level_name": level_name, "project": self.project_code},
                )
                if not existing:
                    doc = frappe.new_doc("GRM Administrative Level Type")
                    doc.level_name = level_name
                    doc.level_order = level_order
                    doc.project = self.project_code
                    doc.insert()
                    self.log.info(f"Created administrative level: {level_name} (order: {level_order})")
                    self.total_created += 1
                self.created_levels[level_name] = level_order
            return True
        except Exception as exc:
            self._record_error(f"Error creating administrative levels: {exc}")
            return False

    def _create_highest_level_region(self) -> bool:
        try:
            highest_level_doc = frappe.db.get_value(
                "GRM Administrative Level Type",
                {"project": self.project_code, "level_name": self.highest_level},
                "name",
            )
            if not highest_level_doc:
                self._record_error(
                    f"Highest level type not found for project {self.project_code}: {self.highest_level}"
                )
                return False

            existing = frappe.db.exists(
                "GRM Administrative Region",
                {
                    "region_name": self.highest_level,
                    "project": self.project_code,
                    "administrative_level": highest_level_doc,
                },
            )
            if existing:
                self.created_regions[self.highest_level] = existing
                self.path_to_region[self.highest_level] = existing
                return True

            doc = frappe.new_doc("GRM Administrative Region")
            doc.region_name = self.highest_level
            doc.administrative_level = highest_level_doc
            doc.project = self.project_code
            doc.parent_region = None
            doc.path = self.highest_level
            doc.insert()

            self.created_regions[self.highest_level] = doc.name
            self.path_to_region[self.highest_level] = doc.name
            self.total_created += 1
            return True
        except Exception as exc:
            self._record_error(f"Error creating highest level region: {exc}")
            return False

    def _create_hierarchical_regions(self) -> bool:
        try:
            for level_index in range(len(self.level_names)):
                if not self._process_level(level_index):
                    return False
            return True
        except Exception as exc:
            self._record_error(f"Error creating hierarchical regions: {exc}")
            return False

    def _process_level(self, level_index: int) -> bool:
        try:
            for region_info in self._get_regions_at_level(level_index):
                if not self._create_region_at_level(region_info, level_index):
                    return False
            return True
        except Exception as exc:
            self._record_error(f"Error processing level {level_index}: {exc}")
            return False

    def _get_regions_at_level(self, level_index: int) -> list[dict]:
        regions: list[dict] = []

        def traverse(node: dict, current_path_parts: list[str], current_level: int) -> None:
            if current_level == level_index:
                for region_name, _region_data in node.items():
                    if region_name.startswith("_"):
                        continue
                    full_path_parts = current_path_parts + [region_name]
                    path = ":".join([self.highest_level] + full_path_parts)
                    parent_path = (
                        ":".join([self.highest_level] + current_path_parts)
                        if current_path_parts
                        else self.highest_level
                    )
                    regions.append({
                        "name": region_name,
                        "path": path,
                        "parent_path": parent_path,
                        "full_path_parts": full_path_parts,
                    })
            elif current_level < level_index:
                for region_name, region_data in node.items():
                    if region_name.startswith("_"):
                        continue
                    traverse(region_data["_children"], current_path_parts + [region_name], current_level + 1)

        traverse(self.hierarchy_tree, [], 0)

        unique: dict[str, dict] = {}
        for r in regions:
            unique.setdefault(r["path"], r)
        return list(unique.values())

    def _create_region_at_level(self, region_info: dict, level_index: int) -> bool:
        try:
            region_name = region_info["name"]
            region_path = region_info["path"]
            parent_path = region_info["parent_path"]
            level_name = self.level_names[level_index]

            if region_path in self.path_to_region:
                return True

            parent_region_id = self.path_to_region.get(parent_path)
            if not parent_region_id:
                self._record_error(f"Parent region not found for path: {parent_path}")
                return False

            existing = frappe.db.exists(
                "GRM Administrative Region",
                {
                    "region_name": region_name,
                    "parent_region": parent_region_id,
                    "project": self.project_code,
                },
            )
            if existing:
                self.path_to_region[region_path] = existing
                self.total_updated += 1
                return True

            level_doc_name = frappe.db.get_value(
                "GRM Administrative Level Type",
                {"project": self.project_code, "level_name": level_name},
                "name",
            )
            if not level_doc_name:
                self._record_error(
                    f"Admin level type not found for project {self.project_code}: {level_name}"
                )
                return False

            doc = frappe.new_doc("GRM Administrative Region")
            doc.region_name = region_name
            doc.administrative_level = level_doc_name
            doc.parent_region = parent_region_id
            doc.project = self.project_code
            doc.path = region_path
            doc.insert()

            self.path_to_region[region_path] = doc.name
            self.total_created += 1
            return True
        except Exception as exc:
            self._record_error(f"Error creating region {region_info}: {exc}")
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _record_error(self, msg: str) -> None:
        self.errors.append(msg)
        try:
            self.log.error(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Slim public API for the wizard RPC + tests
# ---------------------------------------------------------------------------

def parse_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Parse + validate CSV. Returns ``{'preview': [...], 'errors': [...]}``.

    Does NOT touch the database — safe for a wizard preview pane.
    """
    proc = HierarchicalAdminProcessor(project_code=project, highest_level=highest_level)
    return proc.parse_only(csv_text)


def import_csv(project: str, highest_level: str, csv_text: str) -> dict:
    """Parse + validate + insert. Returns ``{'created': N, 'updated': N, 'errors': [...]}``."""
    proc = HierarchicalAdminProcessor(project_code=project, highest_level=highest_level)
    result = proc.run(csv_text)
    if result.get("ok"):
        frappe.db.commit()
    else:
        frappe.db.rollback()
    return result
