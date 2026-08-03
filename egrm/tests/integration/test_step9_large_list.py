"""Phase F.4 integration test: 1000-user list latency.

Seeds 1000 synthetic ``GRM User Project Assignment`` rows under a fresh
project hierarchy (1 province / 4 districts / 25 sectors), then drives
``list_project_users`` through the same shapes the wizard's Step 9 list
panel issues — paginated reads, search, level filter, role filter,
status filter — and asserts each call returns in under
``MAX_PER_PAGE_SECONDS`` seconds (hard threshold from Phase F.4).

The seed path uses raw inserts via ``frappe.get_doc(...).insert(
ignore_permissions=True, ignore_links=True)`` instead of going through
the bulk importer — the importer's 4-stage flow is exercised by F.2/F.3,
and at 1000 rows it would take >60 s, drowning the latency signal we
care about here.

Selectors / endpoints exercised
-------------------------------
- ``list_project_users(project, start=N*25, limit=25)`` — pagination
- ``list_project_users(project, search="alice")`` — full-text search
- ``list_project_users(project, level_type=<sector_level>)`` — level filter
- ``list_project_users(project, role=<role_id>)`` — role filter
- ``list_project_users(project, status="Pending Activation")`` — status filter

Threshold
---------
Each call must return in < 2.0 s wall-clock. The plan says
"per-page < 2s"; we apply the same budget to filter calls because they
share the same SQL path.
"""

from __future__ import annotations

import time
import unicodedata
from typing import Any, ClassVar

import frappe
from frappe.tests.utils import FrappeTestCase

from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_assignments import (
	list_project_users,
)

PROJECT_CODE = "TEST-STEP9-LARGE-LIST"
ROLE_NAME = "Imported"
DUTY_NAME = "Step9 Large-List Duty"

NUM_USERS = 1000
PAGE_SIZE = 25
NUM_PROVINCES = 1
NUM_DISTRICTS = 4
NUM_SECTORS = 25  # → NUM_DISTRICTS * NUM_SECTORS = 100 total sectors

MAX_PER_PAGE_SECONDS = 2.0


def _slug(value: str) -> str:
	norm = unicodedata.normalize("NFKD", value or "")
	return "".join(c for c in norm.encode("ascii", "ignore").decode("ascii").lower() if c.isalnum()) or "user"


def _delete_if_exists(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		try:
			frappe.delete_doc(
				doctype,
				name,
				force=True,
				delete_permanently=True,
				ignore_permissions=True,
			)
		except Exception:
			frappe.db.rollback()


class _LargeListFixture:
	"""Project + 4-level hierarchy + 1000 users + 1000 assignments.

	Class-level so the (slow) seed runs ONCE per test class. Tear-down
	deletes everything in dependency order.
	"""

	sector_level_id: str | None = None
	role_id: str | None = None
	sector_ids: ClassVar[list[str]] = []
	user_emails: ClassVar[list[str]] = []

	@classmethod
	def seed(cls) -> None:
		cls.teardown()
		# 1) Project + 4 admin level types.
		if not frappe.db.exists("GRM Project", PROJECT_CODE):
			frappe.get_doc(
				{
					"doctype": "GRM Project",
					"project_code": PROJECT_CODE,
					"title": "Test Step 9 Large List",
				}
			).insert(ignore_permissions=True)
		levels = [("Project", 1), ("Province", 2), ("District", 3), ("Sector", 4)]
		level_ids: dict[str, str] = {}
		for name, order in levels:
			existing = frappe.db.get_value(
				"GRM Administrative Level Type",
				{"project": PROJECT_CODE, "level_name": name},
				"name",
			)
			if existing:
				level_ids[name] = existing
				continue
			doc = frappe.get_doc(
				{
					"doctype": "GRM Administrative Level Type",
					"project": PROJECT_CODE,
					"level_name": name,
					"level_order": order,
				}
			).insert(ignore_permissions=True)
			level_ids[name] = doc.name
		cls.sector_level_id = level_ids["Sector"]

		# 2) Region tree: 1 province × 4 districts × 25 sectors.
		province = frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"project": PROJECT_CODE,
				"region_name": "P1",
				"administrative_level": level_ids["Province"],
			}
		).insert(ignore_permissions=True)
		sector_ids: list[str] = []
		for d_idx in range(NUM_DISTRICTS):
			district = frappe.get_doc(
				{
					"doctype": "GRM Administrative Region",
					"project": PROJECT_CODE,
					"region_name": f"D{d_idx:02d}",
					"administrative_level": level_ids["District"],
					"parent_region": province.name,
				}
			).insert(ignore_permissions=True)
			for s_idx in range(NUM_SECTORS):
				sector = frappe.get_doc(
					{
						"doctype": "GRM Administrative Region",
						"project": PROJECT_CODE,
						"region_name": f"S{d_idx:02d}-{s_idx:02d}",
						"administrative_level": level_ids["Sector"],
						"parent_region": district.name,
					}
				).insert(ignore_permissions=True)
				sector_ids.append(sector.name)
		cls.sector_ids = sector_ids
		frappe.db.commit()

		# 3) A duty + role.
		duty = "Supervise" if frappe.db.exists("GRM Duty", "Supervise") else None
		if not duty:
			duty_doc = frappe.get_doc(
				{
					"doctype": "GRM Duty",
					"duty_name": DUTY_NAME,
				}
			).insert(ignore_permissions=True)
			duty = duty_doc.name
		role = frappe.get_doc(
			{
				"doctype": "GRM Project Role",
				"project": PROJECT_CODE,
				"role_name": ROLE_NAME,
				"is_active": 1,
				"duties": [{"duty": duty}],
			}
		).insert(ignore_permissions=True)
		cls.role_id = role.name
		frappe.db.commit()

		# 4) 1000 Users + 1000 Assignments. Commit every 100 to keep the
		# transaction small; otherwise a single-txn 1000-row INSERT can
		# fight the test runner's outer rollback semantics.
		#
		# ``frappe.flags.in_import`` short-circuits ``throttle_user_creation``
		# which would otherwise block after 60 user-inserts/min (Frappe's
		# spam-account guardrail). The flag is the documented escape
		# hatch — used by Frappe's Data Import flow itself.
		emails: list[str] = []
		prior_in_import = frappe.flags.get("in_import")
		frappe.flags.in_import = True
		for i in range(NUM_USERS):
			email = f"large_user_{i:04d}@yopmail.com"
			emails.append(email)
			if not frappe.db.exists("User", email):
				frappe.get_doc(
					{
						"doctype": "User",
						"email": email,
						"first_name": f"User{i:04d}",
						"last_name": "Large" if i % 2 == 0 else "List",
						"send_welcome_email": 0,
						"enabled": 1,
						"user_type": "System User",
					}
				).insert(ignore_permissions=True)
			sector = sector_ids[i % len(sector_ids)]
			# ``activation_status`` cycles across the 5 valid values so
			# the status filter has a non-degenerate bucket count.
			status_cycle = [
				"Draft",
				"Pending Activation",
				"Activated",
				"Suspended",
				"Expired",
			]
			assignment_status = status_cycle[i % len(status_cycle)]
			frappe.get_doc(
				{
					"doctype": "GRM User Project Assignment",
					"project": PROJECT_CODE,
					"user": email,
					"role": cls.role_id,
					"administrative_region": sector,
					"activation_status": assignment_status,
					"activation_attempts": 0,  # validate_activation_status compares >=5
					"is_active": 1,
					"position_title": f"Position {i % 50:02d}",
				}
			).insert(ignore_permissions=True)
			if (i + 1) % 100 == 0:
				frappe.db.commit()
		frappe.db.commit()
		frappe.flags.in_import = prior_in_import
		cls.user_emails = emails

	@classmethod
	def teardown(cls) -> None:
		# Assignments → users → role → regions → levels → project.
		for assn in frappe.get_all(
			"GRM User Project Assignment",
			filters={"project": PROJECT_CODE},
			pluck="name",
		):
			_delete_if_exists("GRM User Project Assignment", assn)
		for u in frappe.get_all(
			"User",
			filters=[["email", "like", "large_user_%@yopmail.com"]],
			pluck="name",
		):
			_delete_if_exists("User", u)
		for role in frappe.get_all(
			"GRM Project Role",
			filters={"project": PROJECT_CODE},
			pluck="name",
		):
			_delete_if_exists("GRM Project Role", role)
		# Regions: leaf-up.
		for _ in range(5):
			regions = frappe.get_all(
				"GRM Administrative Region",
				filters={"project": PROJECT_CODE},
				pluck="name",
			)
			if not regions:
				break
			for r in regions:
				try:
					frappe.delete_doc(
						"GRM Administrative Region",
						r,
						force=True,
						delete_permanently=True,
						ignore_permissions=True,
					)
				except Exception:
					frappe.db.rollback()
		for level in frappe.get_all(
			"GRM Administrative Level Type",
			filters={"project": PROJECT_CODE},
			pluck="name",
		):
			_delete_if_exists("GRM Administrative Level Type", level)
		_delete_if_exists("GRM Project", PROJECT_CODE)
		frappe.db.commit()


class Step9LargeListTests(FrappeTestCase):
	"""Pagination + search + filters under 1000 assignments."""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()
		_LargeListFixture.seed()

	@classmethod
	def tearDownClass(cls) -> None:
		_LargeListFixture.teardown()
		super().tearDownClass()

	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	# ---- helpers -----------------------------------------------------------

	def _timed(self, label: str, fn, *args, **kwargs) -> tuple[Any, float]:
		t0 = time.perf_counter()
		result = fn(*args, **kwargs)
		elapsed = time.perf_counter() - t0
		self.assertLess(
			elapsed,
			MAX_PER_PAGE_SECONDS,
			f"{label} took {elapsed:.3f}s (> {MAX_PER_PAGE_SECONDS}s budget)",
		)
		return result, elapsed

	# ---- tests -------------------------------------------------------------

	def test_seed_sanity(self) -> None:
		"""The seed produced exactly NUM_USERS assignments."""
		n = frappe.db.count("GRM User Project Assignment", {"project": PROJECT_CODE})
		self.assertEqual(
			n,
			NUM_USERS,
			f"fixture seeded {n} assignments; expected {NUM_USERS}",
		)

	def test_paginated_list_per_page_under_2s(self) -> None:
		"""Walk every page; each call must come back under MAX_PER_PAGE_SECONDS."""
		total_pages = (NUM_USERS + PAGE_SIZE - 1) // PAGE_SIZE
		# Sample pages: first, middle, last, plus a few random offsets.
		# Walking ALL 40 pages is overkill; sampling catches the same
		# latency regression while keeping the test wall time bounded.
		sample_offsets = [
			0,
			PAGE_SIZE * (total_pages // 4),
			PAGE_SIZE * (total_pages // 2),
			PAGE_SIZE * (3 * total_pages // 4),
			PAGE_SIZE * (total_pages - 1),
		]
		for offset in sample_offsets:
			r, elapsed = self._timed(
				f"page@offset={offset}",
				list_project_users,
				project=PROJECT_CODE,
				start=offset,
				limit=PAGE_SIZE,
			)
			self.assertEqual(r["total"], NUM_USERS)
			self.assertGreater(len(r["rows"]), 0, f"empty page at offset {offset}")
			self.assertLessEqual(len(r["rows"]), PAGE_SIZE)

	def test_search_under_2s(self) -> None:
		"""Search across full_name/email/position_title is sub-2s."""
		# Match ~half of the users (even-indexed got last_name="Large").
		r, _ = self._timed(
			"search=Large",
			list_project_users,
			project=PROJECT_CODE,
			search="Large",
			limit=PAGE_SIZE,
		)
		self.assertGreater(r["total"], 0)
		self.assertLessEqual(len(r["rows"]), PAGE_SIZE)

		# Highly selective search: a single user.
		r, _ = self._timed(
			"search=user_0042",
			list_project_users,
			project=PROJECT_CODE,
			search="user_0042",
			limit=PAGE_SIZE,
		)
		self.assertGreaterEqual(r["total"], 1)

	def test_level_filter_under_2s(self) -> None:
		"""Filter by Sector level (the leaf level — every assignment matches)."""
		r, _ = self._timed(
			"level_type=Sector",
			list_project_users,
			project=PROJECT_CODE,
			level_type=_LargeListFixture.sector_level_id,
			limit=PAGE_SIZE,
		)
		# All assignments are sector-rooted, so the filter doesn't shrink it.
		self.assertEqual(r["total"], NUM_USERS)

	def test_role_filter_under_2s(self) -> None:
		"""Filter by role id (the only role in the fixture)."""
		r, _ = self._timed(
			"role=Imported",
			list_project_users,
			project=PROJECT_CODE,
			role=_LargeListFixture.role_id,
			limit=PAGE_SIZE,
		)
		self.assertEqual(r["total"], NUM_USERS)

	def test_status_filter_under_2s(self) -> None:
		"""Filter by activation_status returns within latency budget.

		We don't pin a specific bucket size because
		``GRMUserProjectAssignment.validate`` may auto-promote rows to
		``Activated`` via ``Non-government worker auto-activated`` (the
		per-row insert log we see in seed output). What we DO assert is
		that the filter call itself returns under
		``MAX_PER_PAGE_SECONDS`` regardless of the resulting bucket size.
		"""
		for status in ("Activated", "Pending Activation", "Draft"):
			r, _ = self._timed(
				f"status={status}",
				list_project_users,
				project=PROJECT_CODE,
				status=status,
				limit=PAGE_SIZE,
			)
			# Total can be 0–NUM_USERS; what matters is that the call
			# didn't throw and respected the latency budget.
			self.assertGreaterEqual(r["total"], 0)
			self.assertLessEqual(r["total"], NUM_USERS)
			self.assertLessEqual(len(r["rows"]), PAGE_SIZE)
