import csv
import logging
import os
import re
from collections import OrderedDict, defaultdict

import click
import frappe
from frappe.commands import get_site, pass_context
from frappe.utils import getdate

from egrm.services.admin_region_importer import HierarchicalAdminProcessor


@click.command("import-admin-regions")
@click.argument("highest_level")
@click.argument("project_code")
@click.argument("csv_file_path")
@click.option("--create-project", is_flag=True, help="Create the project if it doesn't exist")
@click.option(
	"--country-name",
	default="Country",
	help="Name of the country level (highest level)",
)
@pass_context
def import_admin_regions(
	context,
	highest_level,
	project_code,
	csv_file_path,
	create_project=False,
	country_name="Country",
):
	"""
	Import administrative regions from CSV file using hierarchical processing with materialized path.

	HIGHEST_LEVEL: The name of the top-level region (e.g., 'Rwanda', 'PIU')
	PROJECT_CODE: The project code to associate regions with
	CSV_FILE_PATH: Path to the CSV file containing hierarchical data
	"""
	logging.basicConfig(level=logging.INFO)
	log = logging.getLogger("admin_regions")
	frappe.log(f"Starting import for project {project_code} from file {csv_file_path}")
	frappe.log(f"Highest level: {highest_level}")

	try:
		site = get_site(context)
		frappe.init(site=site)
		frappe.connect()

		# Check if the project exists
		if not frappe.db.exists("GRM Project", project_code):
			if create_project:
				create_sample_project(project_code)
				click.echo(f"Created project: {project_code}")
			else:
				click.echo(
					f"Project with code {project_code} does not exist. Use --create-project to create it."
				)
				return

		# Check if the CSV file exists
		if not os.path.exists(csv_file_path):
			click.echo(f"CSV file not found at path: {csv_file_path}")
			return

		# Initialize the hierarchical processor
		processor = HierarchicalAdminProcessor(project_code, highest_level, log)

		# Process the CSV file
		success = processor.process_csv(csv_file_path)

		if success:
			frappe.db.commit()
			click.echo(f"Successfully imported administrative regions for project {project_code}")
			click.echo(f"Total regions created: {processor.total_created}")
			click.echo(f"Administrative levels created: {len(processor.created_levels)}")
		else:
			frappe.db.rollback()
			click.echo("Import failed. All changes have been rolled back.")

	except Exception as e:
		import traceback

		click.echo(f"\nError during import: {e!s}")
		click.echo(traceback.format_exc())
		frappe.db.rollback()
		frappe.log_error(f"Import failed: {e!s}")
	finally:
		frappe.destroy()


def create_sample_project(project_code):
	"""
	Create a sample GRM project for testing purposes.
	"""
	try:
		project_doc = frappe.new_doc("GRM Project")
		project_doc.project_code = project_code
		project_doc.title = f"Sample Project - {project_code}"
		project_doc.description = "Auto-created project for administrative regions import"
		project_doc.is_active = 1
		project_doc.insert()

		return project_doc.name

	except Exception as e:
		frappe.throw(f"Error creating sample project: {e!s}")


# Utility functions for testing and validation


def validate_csv_structure(csv_file_path):
	"""
	Validate CSV structure without creating anything.
	"""
	try:
		with open(csv_file_path, encoding="utf-8") as csvfile:
			reader = csv.reader(csvfile)
			headers = next(reader)

			print(f"Headers detected: {headers}")
			print(f"Number of hierarchy levels: {len(headers)}")

			# Sample first few rows
			for i, row in enumerate(reader):
				if i >= 5:  # Show first 5 rows
					break
				print(f"Row {i+2}: {row}")

	except Exception as e:
		print(f"Error validating CSV: {e!s}")


def preview_hierarchy(csv_file_path, highest_level):
	"""
	Preview the hierarchy that would be created without actually creating it.
	"""
	try:
		with open(csv_file_path, encoding="utf-8") as fh:
			csv_text = fh.read()
		processor = HierarchicalAdminProcessor("PREVIEW", highest_level, logging.getLogger())
		result = processor.parse_only(csv_text)

		print(f"Highest Level: {highest_level}")
		print(f"CSV Levels: {result['level_columns']}")
		print(f"Total rows: {result['total_rows']}")
		if result.get("errors"):
			print("Errors:")
			for err in result["errors"][:10]:
				print(f"  - {err}")
		print("Sample preview rows:")
		for row in result["preview"][:10]:
			print(f"  {row}")

	except Exception as e:
		print(f"Error previewing hierarchy: {e!s}")


commands = [import_admin_regions]
