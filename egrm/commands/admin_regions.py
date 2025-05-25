import csv
import logging
import os
import re
from collections import OrderedDict, defaultdict

import click
import frappe
from frappe.commands import get_site, pass_context
from frappe.utils import getdate


@click.command("import-admin-regions")
@click.argument("highest_level")
@click.argument("project_code")
@click.argument("csv_file_path")
@click.option(
    "--create-project", is_flag=True, help="Create the project if it doesn't exist"
)
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
    log.info(f"Starting import for project {project_code} from file {csv_file_path}")
    log.info(f"Highest level: {highest_level}")

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
            click.echo(
                f"Successfully imported administrative regions for project {project_code}"
            )
            click.echo(f"Total regions created: {processor.total_created}")
            click.echo(
                f"Administrative levels created: {len(processor.created_levels)}"
            )
        else:
            frappe.db.rollback()
            click.echo("Import failed. All changes have been rolled back.")

    except Exception as e:
        import traceback

        click.echo(f"\nError during import: {str(e)}")
        click.echo(traceback.format_exc())
        frappe.db.rollback()
        log.error(f"Import failed: {str(e)}")
    finally:
        frappe.destroy()


class HierarchicalAdminProcessor:
    """
    Processes administrative regions using hierarchical approach with materialized paths.
    """

    def __init__(self, project_code, highest_level, logger):
        self.project_code = project_code
        self.highest_level = highest_level
        self.log = logger
        self.hierarchy_tree = {}
        self.level_names = []
        self.created_levels = {}
        self.created_regions = {}
        self.path_to_region = {}
        self.total_created = 0

    def process_csv(self, csv_file_path):
        """
        Main processing method that orchestrates the entire import process.
        """
        try:
            # Step 1: Parse CSV and build hierarchy tree
            if not self._parse_csv_file(csv_file_path):
                return False

            # Step 2: Create administrative levels
            if not self._create_administrative_levels():
                return False

            # Step 3: Create the highest level region (manually specified)
            if not self._create_highest_level_region():
                return False

            # Step 4: Create all sub-regions using hierarchical processing
            if not self._create_hierarchical_regions():
                return False

            self.log.info("Successfully completed hierarchical processing")
            return True

        except Exception as e:
            self.log.error(f"Error in process_csv: {str(e)}")
            return False

    def _parse_csv_file(self, csv_file_path):
        """
        Parse CSV file and build internal hierarchy tree structure.
        """
        try:
            self.log.info("Parsing CSV file...")

            with open(csv_file_path, "r", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)

                # Read headers
                try:
                    headers = next(reader)
                except StopIteration:
                    self.log.error("CSV file is empty or has no headers")
                    return False

                # Validate headers
                if not headers or len(headers) < 1:
                    self.log.error("CSV file must have at least one column")
                    return False

                # Store level names (columns represent hierarchy levels)
                self.level_names = [header.strip() for header in headers]
                self.log.info(f"Detected hierarchy levels: {self.level_names}")

                # Build hierarchy tree
                row_count = 0
                for row_num, row in enumerate(reader, start=2):
                    if not row or all(cell.strip() == "" for cell in row):
                        continue  # Skip empty rows

                    if len(row) != len(headers):
                        self.log.warning(
                            f"Row {row_num} has {len(row)} columns, expected {len(headers)}. Skipping."
                        )
                        continue

                    # Clean and validate row data
                    clean_row = [cell.strip() for cell in row]
                    if not self._validate_row_data(clean_row, row_num):
                        continue

                    # Add to hierarchy tree
                    self._add_to_hierarchy_tree(clean_row)
                    row_count += 1

                self.log.info(f"Processed {row_count} rows from CSV")
                self.log.info(
                    f"Built hierarchy tree with {len(self.hierarchy_tree)} root nodes"
                )

                return row_count > 0

        except Exception as e:
            self.log.error(f"Error parsing CSV file: {str(e)}")
            return False

    def _validate_row_data(self, row, row_num):
        """
        Validate individual row data.
        """
        # Check for empty values in the hierarchy
        for i, value in enumerate(row):
            if not value:
                self.log.warning(
                    f"Row {row_num}: Empty value at level '{self.level_names[i]}'. Skipping row."
                )
                return False

        # Check for valid characters (basic validation)
        for value in row:
            if len(value) > 140:  # Frappe Data field limit
                self.log.warning(
                    f"Row {row_num}: Value '{value[:50]}...' is too long (>140 chars). Skipping row."
                )
                return False

        return True

    def _add_to_hierarchy_tree(self, row):
        """
        Add a row to the internal hierarchy tree structure.
        """
        current_level = self.hierarchy_tree
        path_parts = []

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

    def _create_administrative_levels(self):
        """
        Create administrative level types for the project.
        """
        try:
            self.log.info("Creating administrative levels...")

            # Create the highest level first (manually specified)
            highest_level_name = self.highest_level.strip()

            # Check if highest level already exists
            existing_highest = frappe.db.exists(
                "GRM Administrative Level Type",
                {"level_name": highest_level_name, "project": self.project_code},
            )

            if not existing_highest:
                highest_doc = frappe.new_doc("GRM Administrative Level Type")
                highest_doc.level_name = highest_level_name
                highest_doc.level_order = 0  # Highest level has order 0
                highest_doc.project = self.project_code
                highest_doc.insert()
                self.log.info(
                    f"Created highest administrative level: {highest_level_name}"
                )
            else:
                self.log.info(
                    f"Highest administrative level already exists: {highest_level_name}"
                )

            self.created_levels[highest_level_name] = 0

            # Create levels for each CSV column
            for i, level_name in enumerate(self.level_names):
                level_order = i + 1  # CSV levels start from order 1

                existing = frappe.db.exists(
                    "GRM Administrative Level Type",
                    {"level_name": level_name, "project": self.project_code},
                )

                if not existing:
                    level_doc = frappe.new_doc("GRM Administrative Level Type")
                    level_doc.level_name = level_name
                    level_doc.level_order = level_order
                    level_doc.project = self.project_code
                    level_doc.insert()
                    self.log.info(
                        f"Created administrative level: {level_name} (order: {level_order})"
                    )
                else:
                    self.log.info(f"Administrative level already exists: {level_name}")

                self.created_levels[level_name] = level_order

            return True

        except Exception as e:
            self.log.error(f"Error creating administrative levels: {str(e)}")
            return False

    def _create_highest_level_region(self):
        """
        Create the highest level region (manually specified by user).
        """
        try:
            self.log.info(f"Creating highest level region: {self.highest_level}")

            # Check if highest level region already exists
            existing = frappe.db.exists(
                "GRM Administrative Region",
                {
                    "region_name": self.highest_level,
                    "project": self.project_code,
                    "administrative_level": self.highest_level,
                },
            )

            if existing:
                self.log.info(
                    f"Highest level region already exists: {self.highest_level}"
                )
                self.created_regions[self.highest_level] = existing
                self.path_to_region[self.highest_level] = existing
                return True

            # Create new highest level region
            region_doc = frappe.new_doc("GRM Administrative Region")
            region_doc.region_name = self.highest_level
            region_doc.administrative_level = self.highest_level
            region_doc.project = self.project_code
            region_doc.parent_region = None  # No parent for highest level
            region_doc.path = self.highest_level  # Materialized path

            region_doc.insert()

            self.created_regions[self.highest_level] = region_doc.name
            self.path_to_region[self.highest_level] = region_doc.name
            self.total_created += 1

            self.log.info(
                f"Created highest level region: {self.highest_level} -> {region_doc.name}"
            )
            return True

        except Exception as e:
            self.log.error(f"Error creating highest level region: {str(e)}")
            return False

    def _create_hierarchical_regions(self):
        """
        Create all regions using hierarchical processing (breadth-first approach).
        """
        try:
            self.log.info("Creating hierarchical regions...")

            # Process each level from top to bottom
            for level_index in range(len(self.level_names)):
                level_name = self.level_names[level_index]
                self.log.info(f"Processing level {level_index + 1}: {level_name}")

                if not self._process_level(level_index):
                    return False

            return True

        except Exception as e:
            self.log.error(f"Error creating hierarchical regions: {str(e)}")
            return False

    def _process_level(self, level_index):
        """
        Process a specific hierarchy level and create all regions at that level.
        """
        try:
            level_name = self.level_names[level_index]
            regions_at_level = self._get_regions_at_level(level_index)

            self.log.info(
                f"Found {len(regions_at_level)} unique regions at level {level_name}"
            )

            for region_info in regions_at_level:
                if not self._create_region_at_level(region_info, level_index):
                    return False

            return True

        except Exception as e:
            self.log.error(f"Error processing level {level_index}: {str(e)}")
            return False

    def _get_regions_at_level(self, level_index):
        """
        Get all unique regions at a specific level with their path information.
        """
        regions = []

        def traverse_tree(node, current_path_parts, current_level):
            if current_level == level_index:
                # We're at the target level
                for region_name, region_data in node.items():
                    if not region_name.startswith("_"):  # Skip metadata
                        full_path_parts = current_path_parts + [region_name]
                        path = ":".join([self.highest_level] + full_path_parts)
                        parent_path = (
                            ":".join([self.highest_level] + current_path_parts)
                            if current_path_parts
                            else self.highest_level
                        )

                        regions.append(
                            {
                                "name": region_name,
                                "path": path,
                                "parent_path": parent_path,
                                "full_path_parts": full_path_parts,
                            }
                        )
            elif current_level < level_index:
                # Keep traversing deeper
                for region_name, region_data in node.items():
                    if not region_name.startswith("_"):  # Skip metadata
                        traverse_tree(
                            region_data["_children"],
                            current_path_parts + [region_name],
                            current_level + 1,
                        )

        traverse_tree(self.hierarchy_tree, [], 0)

        # Remove duplicates based on path
        unique_regions = {}
        for region in regions:
            if region["path"] not in unique_regions:
                unique_regions[region["path"]] = region

        return list(unique_regions.values())

    def _create_region_at_level(self, region_info, level_index):
        """
        Create a specific region at a given level.
        """
        try:
            region_name = region_info["name"]
            region_path = region_info["path"]
            parent_path = region_info["parent_path"]
            level_name = self.level_names[level_index]

            # Check if region already exists
            if region_path in self.path_to_region:
                return True  # Already created

            # Find parent region
            parent_region_id = None
            if parent_path in self.path_to_region:
                parent_region_id = self.path_to_region[parent_path]
            else:
                self.log.error(f"Parent region not found for path: {parent_path}")
                return False

            # Check for existing region with same name under same parent
            existing = frappe.db.exists(
                "GRM Administrative Region",
                {
                    "region_name": region_name,
                    "parent_region": parent_region_id,
                    "project": self.project_code,
                },
            )

            if existing:
                self.log.info(
                    f"Region already exists: {region_name} under {parent_path}"
                )
                self.path_to_region[region_path] = existing
                return True

            # Create new region
            region_doc = frappe.new_doc("GRM Administrative Region")
            region_doc.region_name = region_name
            region_doc.administrative_level = level_name
            region_doc.parent_region = parent_region_id
            region_doc.project = self.project_code
            region_doc.path = region_path  # Materialized path

            region_doc.insert()

            self.path_to_region[region_path] = region_doc.name
            self.total_created += 1

            self.log.info(
                f"Created region: {region_name} at level {level_name} -> {region_doc.name}"
            )
            return True

        except Exception as e:
            self.log.error(f"Error creating region {region_info}: {str(e)}")
            return False



def create_sample_project(project_code):
    """
    Create a sample GRM project for testing purposes.
    """
    try:
        project_doc = frappe.new_doc("GRM Project")
        project_doc.project_code = project_code
        project_doc.title = f"Sample Project - {project_code}"
        project_doc.description = (
            f"Auto-created project for administrative regions import"
        )
        project_doc.is_active = 1
        project_doc.insert()

        return project_doc.name

    except Exception as e:
        frappe.throw(f"Error creating sample project: {str(e)}")


# Utility functions for testing and validation


def validate_csv_structure(csv_file_path):
    """
    Validate CSV structure without creating anything.
    """
    try:
        with open(csv_file_path, "r", encoding="utf-8") as csvfile:
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
        print(f"Error validating CSV: {str(e)}")


def preview_hierarchy(csv_file_path, highest_level):
    """
    Preview the hierarchy that would be created without actually creating it.
    """
    try:
        processor = HierarchicalAdminProcessor(
            "PREVIEW", highest_level, logging.getLogger()
        )
        processor._parse_csv_file(csv_file_path)

        print(f"Highest Level: {highest_level}")
        print(f"CSV Levels: {processor.level_names}")
        print(f"Sample hierarchy paths:")

        # Show some example paths
        count = 0

        def show_paths(node, current_path):
            nonlocal count
            if count >= 10:  # Limit output
                return

            for name, data in node.items():
                if name.startswith("_"):
                    continue

                path = (
                    f"{highest_level}:{current_path}:{name}"
                    if current_path
                    else f"{highest_level}:{name}"
                )
                print(f"  {path}")
                count += 1

                if count < 10:
                    show_paths(
                        data["_children"],
                        f"{current_path}:{name}" if current_path else name,
                    )

        show_paths(processor.hierarchy_tree, "")

    except Exception as e:
        print(f"Error previewing hierarchy: {str(e)}")


commands = [import_admin_regions]
