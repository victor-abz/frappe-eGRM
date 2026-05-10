"""Unit tests for the Phase B Data Import wrapper endpoints.

Covers ``prepare_user_import``, ``poll_user_import``, and
``download_user_template`` from
``egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import``.

``start_user_import`` is intentionally NOT exercised here because it
enqueues a real Frappe background job — covered by the walker
integration test in Phase F.3 instead.

Uses ``frappe.tests.utils.FrappeTestCase`` so the bench test runner
discovers it (the runner is unittest-based, not pytest).
"""

from __future__ import annotations

import csv
import io
import os
import time

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.file_manager import save_file

from egrm.egrm.page.grm_project_wizard.grm_project_wizard_user_data_import import (
    download_user_template,
    poll_user_import,
    prepare_user_import,
)

PROJECT_CODE = "TEST-USER-DATA-IMPORT-A"

LEVELS = [
    ("Province", 1),
    ("District", 2),
    ("Sector", 3),
]


def _delete_if_exists(doctype: str, name: str) -> None:
    if frappe.db.exists(doctype, name):
        try:
            frappe.delete_doc(
                doctype, name, force=True, delete_permanently=True, ignore_permissions=True,
            )
        except Exception:
            frappe.db.rollback()


class _ProjectFixture:
    """Helpers shared by all test classes — seeds a 3-level project."""

    @classmethod
    def seed(cls) -> None:
        if not frappe.db.exists("GRM Project", PROJECT_CODE):
            frappe.get_doc({
                "doctype": "GRM Project",
                "project_code": PROJECT_CODE,
                "title": "Test User Data Import",
            }).insert(ignore_permissions=True)
        for level_name, level_order in LEVELS:
            if not frappe.db.exists(
                "GRM Administrative Level Type",
                {"project": PROJECT_CODE, "level_name": level_name},
            ):
                frappe.get_doc({
                    "doctype": "GRM Administrative Level Type",
                    "project": PROJECT_CODE,
                    "level_name": level_name,
                    "level_order": level_order,
                }).insert(ignore_permissions=True)
        frappe.db.commit()

    @classmethod
    def teardown(cls) -> None:
        # Drop regions first (FK chain); then level types; then project.
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": PROJECT_CODE},
            pluck="name",
        )
        for _ in range(len(LEVELS) + 1):
            for r in list(regions):
                try:
                    frappe.delete_doc(
                        "GRM Administrative Region", r,
                        force=True, delete_permanently=True, ignore_permissions=True,
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


def _save_inline_csv(content: str) -> str:
    """Write ``content`` as a private ``File`` and return its ``file_url``."""
    fname = f"test_user_import_{int(time.time() * 1000)}.csv"
    f = save_file(
        fname=fname,
        content=content.encode("utf-8"),
        dt=None,
        dn=None,
        folder="Home/Attachments",
        is_private=1,
    )
    return f.file_url


_STANDARD_HEADER_MAPPING = {
    "Email": "User.email",
    "First Name": "User.first_name",
    "Last Name": "User.last_name",
    "Username": "Assignment.user",
    "Role": "Assignment.role",
    "Province": "administrative_region",
    "District": "administrative_region",
    "Sector": "administrative_region",
}

_STANDARD_LEVEL_MAPPING = {
    "Province": "Province",
    "District": "District",
    "Sector": "Sector",
}

_STANDARD_HEADERS_LINE = "Email,First Name,Last Name,Username,Role,Province,District,Sector"


class PrepareUserImportTests(FrappeTestCase):
    """Happy-path + dry-run + validation tests for ``prepare_user_import``."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ProjectFixture.teardown()
        _ProjectFixture.seed()

    @classmethod
    def tearDownClass(cls) -> None:
        _ProjectFixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        # Set caller to Administrator so _require_wizard_role passes.
        frappe.set_user("Administrator")
        # Track Data Import docs we create so tearDown can clean them up.
        self._data_imports: list[str] = []
        self._staged_files: list[str] = []
        # Drop any leftover regions for hermetic test runs.
        regions = frappe.get_all(
            "GRM Administrative Region",
            filters={"project": PROJECT_CODE},
            pluck="name",
        )
        for _ in range(len(LEVELS) + 1):
            for r in list(regions):
                try:
                    frappe.delete_doc(
                        "GRM Administrative Region", r,
                        force=True, delete_permanently=True, ignore_permissions=True,
                    )
                    regions.remove(r)
                except Exception:
                    frappe.db.rollback()
        frappe.db.commit()

    def tearDown(self) -> None:
        for di in self._data_imports:
            _delete_if_exists("Data Import", di)
        for path in self._staged_files:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        frappe.db.commit()
        super().tearDown()

    def test_prepare_user_import_creates_data_import(self) -> None:
        """Happy path: small CSV, auto_create_regions=True → Data Import created."""
        csv_content = (
            f"{_STANDARD_HEADERS_LINE}\n"
            "alice@example.com,Alice,Aaron,alice,GRM Officer,Kigali,Gasabo,Kacyiru\n"
            "bob@example.com,Bob,Brown,bob,GRM Officer,Kigali,Nyarugenge,Nyamirambo\n"
        )
        file_url = _save_inline_csv(csv_content)

        result = prepare_user_import(
            project=PROJECT_CODE,
            file_url=file_url,
            header_mapping=_STANDARD_HEADER_MAPPING,
            level_mapping=_STANDARD_LEVEL_MAPPING,
            auto_create_regions=True,
        )

        # Track for teardown.
        self._data_imports.append(result["data_import"])

        self.assertTrue(result["data_import"], "should return a Data Import name")
        self.assertTrue(frappe.db.exists("Data Import", result["data_import"]))
        self.assertEqual(result["rows_total"], 2)
        self.assertEqual(result["rows_ready"], 2)
        self.assertEqual(result["rows_skipped"], 0)

        # Verify the Data Import doc has the correct reference + import file.
        di = frappe.get_doc("Data Import", result["data_import"])
        self.assertEqual(di.reference_doctype, "GRM User Project Assignment")
        self.assertEqual(di.import_type, "Insert New Records")
        self.assertTrue(di.import_file, "Data Import.import_file must be set")
        self.assertIn("/private/files/", di.import_file)

    def test_prepare_user_import_dryrun_lists_regions(self) -> None:
        """auto_create_regions=False with a row whose region doesn't exist
        → ``regions_to_create`` is non-empty and the row is skipped.

        With zero ready rows, no ``Data Import`` doc is created (Frappe
        would reject a zero-row template); ``data_import`` is ``None``
        in the response so the wizard UI knows to prompt for re-submit.
        """
        csv_content = (
            f"{_STANDARD_HEADERS_LINE}\n"
            "ghost@example.com,Ghost,Town,ghost,GRM Officer,Nowhere,Nope,Nada\n"
        )
        file_url = _save_inline_csv(csv_content)

        result = prepare_user_import(
            project=PROJECT_CODE,
            file_url=file_url,
            header_mapping=_STANDARD_HEADER_MAPPING,
            level_mapping=_STANDARD_LEVEL_MAPPING,
            auto_create_regions=False,
        )
        if result["data_import"]:
            self._data_imports.append(result["data_import"])

        self.assertTrue(
            result["regions_to_create"],
            f"dry-run with missing regions must list them; got {result['regions_to_create']!r}",
        )
        self.assertEqual(result["rows_ready"], 0)
        self.assertEqual(result["rows_skipped"], 1)
        self.assertIsNone(result["data_import"], "no Data Import for zero ready rows")

    def test_prepare_user_import_validates_required(self) -> None:
        """Mapping missing the required ``Assignment.role`` field must raise
        ``ValidationError`` and NOT create a Data Import doc."""
        csv_content = (
            "Email,First Name,Last Name,Username\n"
            "x@example.com,X,Y,xy\n"
        )
        file_url = _save_inline_csv(csv_content)

        # Missing User.role — wizard-required for the Assignment.
        bad_mapping = {
            "Email": "User.email",
            "First Name": "User.first_name",
            "Last Name": "User.last_name",
            "Username": "Assignment.user",
        }
        before_count = frappe.db.count("Data Import")

        with self.assertRaises(frappe.ValidationError) as ctx:
            prepare_user_import(
                project=PROJECT_CODE,
                file_url=file_url,
                header_mapping=bad_mapping,
                level_mapping={},
                auto_create_regions=True,
            )
        # The error message must mention what's missing so the UI can
        # show it to the operator.
        self.assertIn("Mapping is invalid", str(ctx.exception))

        # No Data Import doc should have been created.
        after_count = frappe.db.count("Data Import")
        self.assertEqual(
            before_count, after_count,
            "validation failure must not create a Data Import doc",
        )

    def test_prepare_user_import_accepts_json_string_args(self) -> None:
        """RPC may serialize dicts as JSON strings — endpoint must accept them."""
        import json

        csv_content = (
            f"{_STANDARD_HEADERS_LINE}\n"
            "alice@example.com,Alice,Aaron,alice,GRM Officer,Kigali,Gasabo,Kacyiru\n"
        )
        file_url = _save_inline_csv(csv_content)

        result = prepare_user_import(
            project=PROJECT_CODE,
            file_url=file_url,
            header_mapping=json.dumps(_STANDARD_HEADER_MAPPING),
            level_mapping=json.dumps(_STANDARD_LEVEL_MAPPING),
            auto_create_regions="true",  # also exercise truthy-string coercion
        )
        self._data_imports.append(result["data_import"])
        self.assertEqual(result["rows_ready"], 1)


class PollUserImportTests(FrappeTestCase):
    """Smoke test: ``poll_user_import`` returns the documented 5-key dict."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ProjectFixture.teardown()
        _ProjectFixture.seed()

    @classmethod
    def tearDownClass(cls) -> None:
        _ProjectFixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")

    def test_poll_user_import_returns_status_dict(self) -> None:
        """Create a Data Import directly, poll it, assert the 5 keys."""
        # We need a valid import_file for Data Import.validate to pass.
        # Reuse the prepare endpoint to set it up cleanly.
        csv_content = (
            f"{_STANDARD_HEADERS_LINE}\n"
            "alice@example.com,Alice,Aaron,alice,GRM Officer,Kigali,Gasabo,Kacyiru\n"
        )
        file_url = _save_inline_csv(csv_content)
        prepared = prepare_user_import(
            project=PROJECT_CODE,
            file_url=file_url,
            header_mapping=_STANDARD_HEADER_MAPPING,
            level_mapping=_STANDARD_LEVEL_MAPPING,
            auto_create_regions=True,
        )
        di_name = prepared["data_import"]
        try:
            status = poll_user_import(data_import=di_name)
            for key in ("status", "payload_count", "import_log_preview", "succeeded", "failed"):
                self.assertIn(key, status, f"poll_user_import must return key {key!r}")
            # Status before run is "Pending".
            self.assertEqual(status["status"], "Pending")
            self.assertEqual(status["succeeded"], 0)
            self.assertEqual(status["failed"], 0)
            self.assertGreaterEqual(status["payload_count"], 0)
        finally:
            _delete_if_exists("Data Import", di_name)


class DownloadUserTemplateTests(FrappeTestCase):
    """``download_user_template`` writes to ``frappe.response`` directly."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _ProjectFixture.teardown()
        _ProjectFixture.seed()

    @classmethod
    def tearDownClass(cls) -> None:
        _ProjectFixture.teardown()
        super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        frappe.set_user("Administrator")
        # Reset frappe.response so we don't pollute other tests.
        frappe.local.response = frappe._dict()

    def test_download_user_template_csv(self) -> None:
        """CSV format: response carries filename + filecontent starting with level types."""
        download_user_template(project=PROJECT_CODE, format="csv")

        self.assertEqual(
            frappe.response.get("filename"),
            f"user_template_{PROJECT_CODE}.csv",
        )
        content = frappe.response.get("filecontent")
        self.assertIsInstance(content, str)
        # First line is the header row — must start with the level types.
        first_line = content.splitlines()[0]
        reader = csv.reader(io.StringIO(first_line))
        header = next(reader)
        # The first 3 columns must be the project's level types in order.
        self.assertEqual(
            header[:3], ["Province", "District", "Sector"],
            f"template header must start with project level types; got {header!r}",
        )
        # Required User minima must be present somewhere downstream.
        for label in ("Email", "First Name", "Last Name"):
            self.assertIn(label, header)

    def test_download_user_template_xlsx(self) -> None:
        """XLSX format: response is binary; filename has .xlsx extension."""
        download_user_template(project=PROJECT_CODE, format="xlsx")

        self.assertEqual(
            frappe.response.get("filename"),
            f"user_template_{PROJECT_CODE}.xlsx",
        )
        content = frappe.response.get("filecontent")
        self.assertIsInstance(content, (bytes, bytearray))
        # XLSX is a ZIP archive — must start with the ZIP magic bytes.
        self.assertTrue(
            bytes(content).startswith(b"PK"),
            "xlsx response must start with ZIP magic 'PK'",
        )
