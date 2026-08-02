"""Unit tests for ``egrm.services.user_import``.

Exercises ``resolve_region`` against a freshly-seeded 3-level project
hierarchy (Province → District → Sector — names are arbitrary, the code
must work for any project-defined level set), plus light coverage of
``auto_detect_mapping`` and ``validate_mapping``.

Uses ``frappe.tests.utils.FrappeTestCase`` so the bench test runner
discovers it (the runner is unittest-based, not pytest).
"""

from __future__ import annotations

import csv
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.services.user_import import (
	TARGET_REGION,
	TARGET_SKIP,
	auto_detect_mapping,
	materialize_staged_csv,
	resolve_region,
	validate_mapping,
)

PROJECT_CODE = "TEST-USER-IMPORT-A"

LEVELS = [
	("Province", 1),
	("District", 2),
	("Sector", 3),
]


def _delete_if_exists(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		try:
			frappe.delete_doc(doctype, name, force=True, delete_permanently=True, ignore_permissions=True)
		except Exception:
			frappe.db.rollback()


class UserImportRegionTests(FrappeTestCase):
	"""Region-resolution tests — the load-bearing core of the bulk importer."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		cls._teardown_project()
		cls._seed_project()

	@classmethod
	def tearDownClass(cls) -> None:
		cls._teardown_project()
		super().tearDownClass()

	@classmethod
	def _seed_project(cls) -> None:
		if not frappe.db.exists("GRM Project", PROJECT_CODE):
			frappe.get_doc(
				{
					"doctype": "GRM Project",
					"project_code": PROJECT_CODE,
					"title": "Test User Import",
				}
			).insert(ignore_permissions=True)
		for level_name, level_order in LEVELS:
			if not frappe.db.exists(
				"GRM Administrative Level Type",
				{"project": PROJECT_CODE, "level_name": level_name},
			):
				frappe.get_doc(
					{
						"doctype": "GRM Administrative Level Type",
						"project": PROJECT_CODE,
						"level_name": level_name,
						"level_order": level_order,
					}
				).insert(ignore_permissions=True)
		frappe.db.commit()

	@classmethod
	def _teardown_project(cls) -> None:
		# Wipe regions first (FK to level types); then level types; then project.
		regions = frappe.get_all(
			"GRM Administrative Region",
			filters={"project": PROJECT_CODE},
			pluck="name",
		)
		# Delete leaf-up to avoid parent_region FK violations.
		for _ in range(len(LEVELS) + 1):
			for r in list(regions):
				try:
					frappe.delete_doc(
						"GRM Administrative Region",
						r,
						force=True,
						delete_permanently=True,
						ignore_permissions=True,
					)
					regions.remove(r)
				except Exception:
					frappe.db.rollback()
		for level_name, _ in LEVELS:
			level_id = frappe.db.get_value(
				"GRM Administrative Level Type",
				{"project": PROJECT_CODE, "level_name": level_name},
				"name",
			)
			if level_id:
				_delete_if_exists("GRM Administrative Level Type", level_id)
		_delete_if_exists("GRM Project", PROJECT_CODE)
		frappe.db.commit()

	# ------------------------------------------------------------------
	# Test helpers
	# ------------------------------------------------------------------
	def _level_id(self, level_name: str) -> str:
		return frappe.db.get_value(
			"GRM Administrative Level Type",
			{"project": PROJECT_CODE, "level_name": level_name},
			"name",
		)

	def _make_region(self, level_name: str, value: str, parent: str | None) -> str:
		existing = frappe.db.exists(
			"GRM Administrative Region",
			{
				"project": PROJECT_CODE,
				"administrative_level": self._level_id(level_name),
				"region_name": value,
				"parent_region": parent,
			},
		)
		if existing:
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"project": PROJECT_CODE,
				"administrative_level": self._level_id(level_name),
				"region_name": value,
				"parent_region": parent,
			}
		).insert(ignore_permissions=True)
		return doc.name

	def _drop_regions(self) -> None:
		regions = frappe.get_all(
			"GRM Administrative Region",
			filters={"project": PROJECT_CODE},
			pluck="name",
		)
		for _ in range(len(LEVELS) + 1):
			for r in list(regions):
				try:
					frappe.delete_doc(
						"GRM Administrative Region",
						r,
						force=True,
						delete_permanently=True,
						ignore_permissions=True,
					)
					regions.remove(r)
				except Exception:
					frappe.db.rollback()
		frappe.db.commit()

	# ------------------------------------------------------------------
	# Tests
	# ------------------------------------------------------------------
	def test_resolve_region_3_levels_existing(self) -> None:
		self._drop_regions()
		province = self._make_region("Province", "Kigali", None)
		district = self._make_region("District", "Gasabo", province)
		sector = self._make_region("Sector", "Kacyiru", district)

		region_id, created = resolve_region(
			row={"Province": "Kigali", "District": "Gasabo", "Sector": "Kacyiru"},
			level_columns_ordered=[
				("Province", "Kigali"),
				("District", "Gasabo"),
				("Sector", "Kacyiru"),
			],
			project=PROJECT_CODE,
			auto_create=True,
		)
		self.assertEqual(region_id, sector)
		self.assertEqual(created, [], "should not have created any new regions")

	def test_resolve_region_partial_path(self) -> None:
		self._drop_regions()
		province = self._make_region("Province", "Kigali", None)
		district = self._make_region("District", "Gasabo", province)

		region_id, created = resolve_region(
			row={"Province": "Kigali", "District": "Gasabo", "Sector": ""},
			level_columns_ordered=[
				("Province", "Kigali"),
				("District", "Gasabo"),
				("Sector", ""),  # empty cell stops resolution at District
			],
			project=PROJECT_CODE,
			auto_create=True,
		)
		self.assertEqual(region_id, district)
		self.assertEqual(created, [])

	def test_resolve_region_missing_no_autocreate_raises(self) -> None:
		self._drop_regions()
		province = self._make_region("Province", "Kigali", None)
		# District does NOT exist.

		with self.assertRaises(frappe.ValidationError):
			resolve_region(
				row={"Province": "Kigali", "District": "Nyarugenge"},
				level_columns_ordered=[
					("Province", "Kigali"),
					("District", "Nyarugenge"),
				],
				project=PROJECT_CODE,
				auto_create=False,
			)
		# Province should still be the only region; nothing leaked.
		regions = frappe.get_all(
			"GRM Administrative Region",
			filters={"project": PROJECT_CODE},
			pluck="name",
		)
		self.assertEqual(set(regions), {province})

	def test_resolve_region_missing_autocreate_creates_chain(self) -> None:
		self._drop_regions()
		# Nothing exists yet — auto_create must build the whole chain.

		region_id, created = resolve_region(
			row={"Province": "Northern", "District": "Musanze", "Sector": "Muhoza"},
			level_columns_ordered=[
				("Province", "Northern"),
				("District", "Musanze"),
				("Sector", "Muhoza"),
			],
			project=PROJECT_CODE,
			auto_create=True,
		)

		# Three levels created, returned id = leaf.
		self.assertIsNotNone(region_id)
		self.assertEqual(len(created), 3)
		levels_created = [c[0] for c in created]
		self.assertEqual(levels_created, ["Province", "District", "Sector"])

		# Returned id is the Sector row.
		leaf = frappe.get_doc("GRM Administrative Region", region_id)
		self.assertEqual(leaf.region_name, "Muhoza")
		self.assertEqual(
			frappe.db.get_value("GRM Administrative Level Type", leaf.administrative_level, "level_name"),
			"Sector",
		)

		# Parent chain is wired correctly.
		district_doc = frappe.get_doc("GRM Administrative Region", leaf.parent_region)
		self.assertEqual(district_doc.region_name, "Musanze")
		province_doc = frappe.get_doc("GRM Administrative Region", district_doc.parent_region)
		self.assertEqual(province_doc.region_name, "Northern")
		self.assertIsNone(province_doc.parent_region or None)


class UserImportMappingTests(FrappeTestCase):
	"""Lightweight coverage of the auto-detect + validate helpers.

	These don't need a seeded project — they exercise pure functions
	that only consult the doctype meta + a project_meta dict the caller
	constructs.
	"""

	def test_auto_detect_basic_user_and_assignment(self) -> None:
		project_meta = {
			"project_levels": [
				{"level_name": "Province", "level_order": 1, "name": "x1"},
				{"level_name": "District", "level_order": 2, "name": "x2"},
			],
		}
		headers = ["Email", "First Name", "Last Name", "Province", "Role", "Position Title", "Mystery"]
		m = auto_detect_mapping(headers, project_meta)

		self.assertEqual(m["Email"]["target"], "User.email")
		self.assertEqual(m["First Name"]["target"], "User.first_name")
		self.assertEqual(m["Last Name"]["target"], "User.last_name")
		self.assertEqual(m["Province"]["target"], TARGET_REGION)
		self.assertEqual(m["Province"]["level_type"], "Province")
		self.assertEqual(m["Role"]["target"], "Assignment.role")
		self.assertEqual(m["Position Title"]["target"], "Assignment.position_title")
		self.assertEqual(m["Mystery"]["target"], TARGET_SKIP)

	def test_validate_mapping_flags_missing_required(self) -> None:
		# Map only email — first_name/last_name/role missing → should fail.
		mapping = {"Email": {"target": "User.email", "level_type": None}}
		result = validate_mapping(mapping, project_meta={})
		self.assertFalse(result["ok"])
		self.assertTrue(result["missing_required"], "should list missing required fields")

	def test_validate_mapping_passes_when_required_present(self) -> None:
		mapping = {
			"Email": {"target": "User.email", "level_type": None},
			"First Name": {"target": "User.first_name", "level_type": None},
			"Last Name": {"target": "User.last_name", "level_type": None},
			"Username": {"target": "Assignment.user", "level_type": None},
			"Role": {"target": "Assignment.role", "level_type": None},
		}
		result = validate_mapping(mapping, project_meta={})
		self.assertTrue(result["ok"], f"validation should pass; got: {result}")
		self.assertEqual(result["missing_required"], [])
		self.assertEqual(result["errors"], [])

	def test_auto_detect_full_name_header_emits_warning(self) -> None:
		# Header "Full Name" cannot be split deterministically — auto-detect
		# must flag it so the Phase E UI can prompt the user.
		project_meta = {"project_levels": []}
		m = auto_detect_mapping(["Full Name"], project_meta)
		entry = m["Full Name"]
		self.assertEqual(entry["target"], "User.first_name")
		self.assertTrue(entry.get("needs_split"))
		self.assertIsInstance(entry.get("warning"), str)
		self.assertIn("full name", entry["warning"].lower())

	def test_auto_detect_order_matches_plan(self) -> None:
		# Plan order: doctype-label first, level-type second, name-split third.
		# Construct a synthetic project_meta whose level type collides with
		# a real User-doctype field label ("Username") to verify the
		# doctype-first ordering takes precedence.
		project_meta = {
			"project_levels": [
				{"level_name": "Username", "level_order": 1, "name": "x1"},
			],
		}
		m = auto_detect_mapping(["Username"], project_meta)
		# Doctype match must win: User.username, NOT TARGET_REGION.
		self.assertEqual(m["Username"]["target"], "User.username")
		self.assertIsNone(m["Username"]["level_type"])

	def test_validate_mapping_flags_duplicate_level(self) -> None:
		# Two columns mapped to the same admin level type — the mapper
		# should reject this per plan line 116.
		mapping = {
			"Email": {"target": "User.email", "level_type": None},
			"First Name": {"target": "User.first_name", "level_type": None},
			"Last Name": {"target": "User.last_name", "level_type": None},
			"Username": {"target": "Assignment.user", "level_type": None},
			"Role": {"target": "Assignment.role", "level_type": None},
			"Province1": {"target": TARGET_REGION, "level_type": "Province"},
			"Province2": {"target": TARGET_REGION, "level_type": "Province"},
		}
		result = validate_mapping(mapping, project_meta={})
		self.assertFalse(result["ok"])
		self.assertTrue(any("Province" in e for e in result["errors"]))


class UserImportMaterializeTests(FrappeTestCase):
	"""Coverage of ``materialize_staged_csv`` end-to-end (file write).

	Uses the same seeded project as ``UserImportRegionTests`` to keep the
	test footprint small and independent of any wizard plumbing.
	"""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		UserImportRegionTests._teardown_project()
		UserImportRegionTests._seed_project()

	@classmethod
	def tearDownClass(cls) -> None:
		UserImportRegionTests._teardown_project()
		super().tearDownClass()

	def setUp(self) -> None:
		super().setUp()
		self._staged_files: list[str] = []
		# Drop any leftover regions from prior tests so each run is hermetic.
		regions = frappe.get_all(
			"GRM Administrative Region",
			filters={"project": PROJECT_CODE},
			pluck="name",
		)
		for _ in range(len(LEVELS) + 1):
			for r in list(regions):
				try:
					frappe.delete_doc(
						"GRM Administrative Region",
						r,
						force=True,
						delete_permanently=True,
						ignore_permissions=True,
					)
					regions.remove(r)
				except Exception:
					frappe.db.rollback()
		frappe.db.commit()

	def tearDown(self) -> None:
		for path in self._staged_files:
			try:
				if path and os.path.exists(path):
					os.remove(path)
			except OSError:
				pass
		super().tearDown()

	# Standard mapping reused across tests: 3 source columns map to
	# User.email/first_name/last_name + Assignment.user/role + 3 region
	# level columns. validate_mapping would pass for this mapping.
	@staticmethod
	def _standard_mapping() -> dict:
		return {
			"Email": {"target": "User.email", "level_type": None},
			"First Name": {"target": "User.first_name", "level_type": None},
			"Last Name": {"target": "User.last_name", "level_type": None},
			"Username": {"target": "Assignment.user", "level_type": None},
			"Role": {"target": "Assignment.role", "level_type": None},
			"Province": {"target": TARGET_REGION, "level_type": "Province"},
			"District": {"target": TARGET_REGION, "level_type": "District"},
			"Sector": {"target": TARGET_REGION, "level_type": "Sector"},
		}

	@staticmethod
	def _headers() -> list[str]:
		return [
			"Email",
			"First Name",
			"Last Name",
			"Username",
			"Role",
			"Province",
			"District",
			"Sector",
		]

	def test_materialize_happy_path(self) -> None:
		# 2 rows, auto_create_regions=True, no missing pieces.
		rows = [
			["a@example.com", "Alice", "Aaron", "alice", "GRM Officer", "Kigali", "Gasabo", "Kacyiru"],
			["b@example.com", "Bob", "Brown", "bob", "GRM Officer", "Kigali", "Nyarugenge", "Nyamirambo"],
		]
		result = materialize_staged_csv(
			rows=rows,
			headers=self._headers(),
			mapping=self._standard_mapping(),
			project=PROJECT_CODE,
			auto_create_regions=True,
		)
		self._staged_files.append(result["staged_path"])

		self.assertTrue(os.path.exists(result["staged_path"]))
		self.assertEqual(result["rows_total"], 2)
		self.assertEqual(result["rows_ready"], 2)
		self.assertEqual(result["rows_skipped"], 0)
		self.assertEqual(len(result["preview"]), 2)
		for entry in result["preview"]:
			self.assertIsInstance(entry, dict)

		with open(result["staged_path"], encoding="utf-8") as fh:
			reader = csv.reader(fh)
			header_row = next(reader)
			staged_rows = list(reader)
		# Header must include the mapped target fieldnames + administrative_region + project.
		for expected in (
			"email",
			"first_name",
			"last_name",
			"user",
			"role",
			"administrative_region",
			"project",
		):
			self.assertIn(expected, header_row, f"staged header missing {expected!r}: {header_row}")
		self.assertEqual(len(staged_rows), 2)
		# Every staged row must carry the project value so Frappe Data Import
		# can satisfy GRM User Project Assignment's required `project` link.
		project_idx = header_row.index("project")
		for r in staged_rows:
			self.assertEqual(r[project_idx], PROJECT_CODE)

	def test_materialize_dryrun_lists_missing_regions(self) -> None:
		# auto_create_regions=False; no regions seeded → all rows unresolvable.
		rows = [
			["a@example.com", "Alice", "Aaron", "alice", "GRM Officer", "Kigali", "Gasabo", "Kacyiru"],
			["b@example.com", "Bob", "Brown", "bob", "GRM Officer", "Kigali", "Gasabo", "Remera"],
		]
		result = materialize_staged_csv(
			rows=rows,
			headers=self._headers(),
			mapping=self._standard_mapping(),
			project=PROJECT_CODE,
			auto_create_regions=False,
		)
		self._staged_files.append(result["staged_path"])

		# regions_to_create is the dry-run shape: list of (level_type, value) 2-tuples.
		self.assertTrue(result["regions_to_create"])
		for entry in result["regions_to_create"]:
			self.assertEqual(len(entry), 2, f"dry-run regions_to_create must be 2-tuples; got {entry!r}")
			level_type, value = entry
			self.assertIsInstance(level_type, str)
			self.assertIsInstance(value, str)

		# Every row was unresolvable → every row skipped, with documented error format.
		self.assertEqual(result["rows_skipped"], 2)
		self.assertEqual(result["rows_ready"], 0)
		self.assertEqual(len(result["errors"]), 2)
		for err in result["errors"]:
			self.assertIn("does not exist", err)
			self.assertIn("auto_create=False", err)

	def test_materialize_skips_row_with_missing_region_in_dryrun(self) -> None:
		# Locked contract from Issue #3: in dry-run, an unresolvable row is
		# NOT written to the staged CSV (no NULL-region ghosts).
		rows = [
			["a@example.com", "Alice", "Aaron", "alice", "GRM Officer", "Nowhere", "Nope", "Nada"],
		]
		result = materialize_staged_csv(
			rows=rows,
			headers=self._headers(),
			mapping=self._standard_mapping(),
			project=PROJECT_CODE,
			auto_create_regions=False,
		)
		self._staged_files.append(result["staged_path"])

		self.assertEqual(result["rows_ready"], 0)
		self.assertEqual(result["rows_skipped"], 1)

		with open(result["staged_path"], encoding="utf-8") as fh:
			reader = csv.reader(fh)
			next(reader)  # header
			staged_rows = list(reader)
		# Row count in CSV must equal rows_ready (0), not rows_total.
		self.assertEqual(
			len(staged_rows),
			result["rows_ready"],
			f"staged CSV must contain only ready rows; got {len(staged_rows)} body rows",
		)
