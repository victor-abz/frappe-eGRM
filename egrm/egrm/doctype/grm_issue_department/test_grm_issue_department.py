# Copyright (c) 2025, Victor Abizeyimana and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]


class UnitTestGRMIssueDepartment(UnitTestCase):
	"""
	Unit tests for GRMIssueDepartment.
	Use this class for testing individual functions and methods.
	"""

	pass


class IntegrationTestGRMIssueDepartment(IntegrationTestCase):
	"""
	Integration tests for GRMIssueDepartment.
	Use this class for testing interactions between multiple components.
	"""

	pass
