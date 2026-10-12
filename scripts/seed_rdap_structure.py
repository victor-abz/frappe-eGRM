"""Bring the RDAP administrative hierarchy in line with the signed user list.

Source of truth: ``RISA - eGRM Users (RDAP).csv`` (30 rows, 29 people). That
sheet names a Province, District and Sector for every field user, which means
RDAP needs four levels -- PIU, Province, District, Sector -- not the two it was
seeded with. The visible symptom was Rwamagana, a district, sitting in the tree
tagged as a Province: the portal labels each cascade step with the level name
of the rows the API returned (``SubmitPage.tsx:419``), so a citizen filing an
issue in Rwamagana was asked to "Select Province" twice -- "Hitamo Intara"
twice in Kinyarwanda -- the second time from a list of districts.

Only the places the sheet names are created: 16 districts and 21 sectors. The
full Rwandan tree is 14,837 rows, and seeding it would bury 29 users in 416
sectors nobody covers. Every sector the sheet names is created even when the
person posted there is a supervisor who sits at district level, so an issue can
still be filed against that sector.

Three corrections are applied to the sheet, each verified row by row against
``egrm/commands/rwanda_locations.csv`` (30 districts, 417 sectors):

1. Three rows name a district that belongs to a different province than the one
   in their Province column -- Gasabo under Northern and Western, Nyarugenge
   under Southern; all three are Kigali City districts. All three are Digital
   Literacy Training Officers, and one of them (0782331296) appears twice with
   the same home district under two different provinces. So for a DLTO the
   Province column is the area they cover and the District/Sector is where they
   are based. They are assigned to their Province; their home district is still
   created, because it is a real place the sheet names. Every supervisor and
   ambassador row is internally consistent and is taken at face value.
2. ``Cyanya`` (Rwamagana) and ``Kivumu`` (Rubavu) are not sectors -- they are
   cells, of Kigabiro and Gisenyi respectively. They are promoted to their
   sector. A ``Kivumu`` sector does exist, but in Rutsiro, a different province.
3. Casing is normalised to the canonical spelling: MUSANZE/MUHOZA/MUKINDO ->
   Musanze/Muhoza/Mukindo.

Placement follows the position, because region access is "your region and
everything below it" (``grm_issue_permissions.check_region_access``):

    Project Coordinator               -> PIU
    Project Administrator             -> Province
    Digital Literacy Training Officer -> Province (coverage, see 1 above)
    Digital ambassador's supervisor   -> District, so they see every ambassador
                                         under them rather than only the one in
                                         their own sector
    Digital ambassador                -> Sector

The sheet's own "Project Role" column reads "Project Administrator" for all 24
field rows, so it cannot distinguish a supervisor from an ambassador; the
Position column is what carries that, and it is what this script keys on.

Idempotent: re-running makes no changes. Dry run first, then apply::

    bench - -site < site > console < run_seed.py  # calls run(apply=False)
"""

from __future__ import annotations

import logging

import frappe

from egrm.services.user_import import _ensure_user

logger = logging.getLogger(__name__)

PROJECT = "RDAP"

# level_name -> level_order. PIU and Province already exist; District and
# Sector are what the sheet requires and the original seed omitted.
LEVELS: dict[str, int] = {"PIU": 1, "Province": 2, "District": 3, "Sector": 4}

# Province -> District -> [Sector, ...]. Every district and sector the sheet
# names, reparented to its canonical province and with cells promoted to their
# sector. Kayonza carries no sector because its row (17) leaves Sector blank.
TREE: dict[str, dict[str, list[str]]] = {
	"Eastern": {
		"Bugesera": ["Nyamata"],
		"Kayonza": [],
		"Ngoma": ["Kibungo"],
		"Rwamagana": ["Kigabiro"],
	},
	"Kigali city": {
		"Gasabo": ["Gikomero", "Jali", "Kimironko"],
		"Kicukiro": ["Gatenga", "Kagarama"],
		"Nyarugenge": ["Nyakabanda", "Nyarugenge"],
	},
	"Northern": {
		"Burera": ["Kinoni"],
		"Musanze": ["Muhoza"],
		"Rulindo": ["Rukozo", "Shyorongi"],
	},
	"Southern": {
		"Gisagara": ["Mukindo"],
		"Huye": ["Ngoma"],
		"Nyanza": ["Busasamana", "Kibilizi"],
	},
	"Western": {
		"Nyabihu": ["Rambura"],
		"Rubavu": ["Gisenyi"],
		"Rusizi": ["Gashonga"],
	},
}

# One entry per sheet row, in sheet order. ``path`` is the region the
# person is assigned to, root first; it is deliberately shallower than the
# place the row names for coordinators, administrators, DLTOs and
# supervisors. 0782331296 appears twice -- two sheet rows, two provinces,
# one person -- and therefore holds two assignments.
PEOPLE: list[dict[str, str | tuple[str, ...]]] = [
	{
		"email": "0782331296@yopmail.com",
		"path": ("PIU", "Kigali city"),
		"first_name": "Jean Claude",
		"last_name": "HAKIZIMANA",
		"gender": "Male",
		"phone": "782331296",
		"position": "Digital Literacy Training Officer",
		"project_role": "Project Administrator",
	},
	{
		"email": "0788875719@yopmail.com",
		"path": ("PIU", "Kigali city", "Kicukiro"),
		"first_name": "Norbert",
		"last_name": "MUHIRE",
		"gender": "Male",
		"phone": "",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0785448897@yopmail.com",
		"path": ("PIU", "Kigali city", "Nyarugenge"),
		"first_name": "Thérèse",
		"last_name": "NYIRANSENGIMANA",
		"gender": "Female",
		"phone": "785448897",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0784245493@yopmail.com",
		"path": ("PIU", "Kigali city", "Kicukiro", "Gatenga"),
		"first_name": "Clenia",
		"last_name": "DUSABIMANA",
		"gender": "Female",
		"phone": "784245493",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0782767772@yopmail.com",
		"path": ("PIU", "Kigali city", "Gasabo", "Gikomero"),
		"first_name": "Eric",
		"last_name": "BISANABAGABO",
		"gender": "Male",
		"phone": "782767772",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0782331296@yopmail.com",
		"path": ("PIU", "Northern"),
		"first_name": "Jean Claude",
		"last_name": "HAKIZIMANA",
		"gender": "Male",
		"phone": "782331296",
		"position": "Digital Literacy Training Officer",
		"project_role": "Project Administrator",
	},
	{
		"email": "0788706559@yopmail.com",
		"path": ("PIU", "Northern", "Rulindo"),
		"first_name": "René Marcel",
		"last_name": "UWIMANA",
		"gender": "Male",
		"phone": "788706559",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0789492513@yopmail.com",
		"path": ("PIU", "Northern", "Burera", "Kinoni"),
		"first_name": "Obed",
		"last_name": "TUMUSHIME",
		"gender": "Male",
		"phone": "789492513",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0783362192@yopmail.com",
		"path": ("PIU", "Northern", "Rulindo", "Rukozo"),
		"first_name": "Bernardine",
		"last_name": "INGABIRE",
		"gender": "Female",
		"phone": "783362192",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0787677235@yopmail.com",
		"path": ("PIU", "Northern", "Musanze"),
		"first_name": "Henriette",
		"last_name": "CYIZA",
		"gender": "Female",
		"phone": "787677235",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0785760112@yopmail.com",
		"path": ("PIU", "Southern"),
		"first_name": "Ezechias",
		"last_name": "IRAMBONA",
		"gender": "Male",
		"phone": "785760112",
		"position": "Digital Literacy Training Officer",
		"project_role": "Project Administrator",
	},
	{
		"email": "0788876531@yopmail.com",
		"path": ("PIU", "Southern", "Huye"),
		"first_name": "Olivier",
		"last_name": "BATENDA",
		"gender": "Male",
		"phone": "788876531",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0783348299@yopmail.com",
		"path": ("PIU", "Southern", "Nyanza"),
		"first_name": "Angelique",
		"last_name": "HUMURE",
		"gender": "Female",
		"phone": "783348299",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "07811317195@yopmail.com",
		"path": ("PIU", "Southern", "Gisagara", "Mukindo"),
		"first_name": "Jeannine",
		"last_name": "NYIRANEZA",
		"gender": "Female",
		"phone": "7811317195",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0789055942@yopmail.com",
		"path": ("PIU", "Southern", "Nyanza", "Kibilizi"),
		"first_name": "Emile",
		"last_name": "IRADUKUNDA",
		"gender": "Male",
		"phone": "789055942",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0782855690@yopmail.com",
		"path": ("PIU", "Eastern", "Kayonza"),
		"first_name": "Erneste",
		"last_name": "NIYOMUFASHA",
		"gender": "Male",
		"phone": "782855690",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0780049833@yopmail.com",
		"path": ("PIU", "Eastern", "Rwamagana"),
		"first_name": "Justine",
		"last_name": "MUGAMBIRA",
		"gender": "Female",
		"phone": "780049833",
		"position": "Digital Ambassador’s Supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0781733177@yopmail.com",
		"path": ("PIU", "Eastern", "Ngoma", "Kibungo"),
		"first_name": "Agnes",
		"last_name": "MUTANGAMPUNDU",
		"gender": "Female",
		"phone": "781733177",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0781911838@yopmail.com",
		"path": ("PIU", "Eastern", "Bugesera", "Nyamata"),
		"first_name": "Fisto",
		"last_name": "SHIRIMPAKA",
		"gender": "Male",
		"phone": "781911838",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0782346691@yopmail.com",
		"path": ("PIU", "Western"),
		"first_name": "Immaculee",
		"last_name": "IMANISHIMWE",
		"gender": "Female",
		"phone": "782346691",
		"position": "Digital Literacy Training Officer",
		"project_role": "Project Administrator",
	},
	{
		"email": "0785610631@yopmail.com",
		"path": ("PIU", "Western", "Rusizi"),
		"first_name": "Andre",
		"last_name": "NGENDAHAYO",
		"gender": "Male",
		"phone": "785610631",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0781282506@yopmail.com",
		"path": ("PIU", "Western", "Rubavu"),
		"first_name": "Gentille Scholastique",
		"last_name": "NYINAWABERA",
		"gender": "Female",
		"phone": "781282506",
		"position": "Digital ambassador’s supervisor",
		"project_role": "Project Administrator",
	},
	{
		"email": "0784016323@yopmail.com",
		"path": ("PIU", "Western", "Nyabihu", "Rambura"),
		"first_name": "Annoncée",
		"last_name": "MUKARUYENZI",
		"gender": "Female",
		"phone": "784016323",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "0787979743@yopmail.com",
		"path": ("PIU", "Western", "Rubavu", "Gisenyi"),
		"first_name": "Theoneste",
		"last_name": "MPAYIMANA",
		"gender": "Male",
		"phone": "787979743",
		"position": "Digital ambassador",
		"project_role": "Project Administrator",
	},
	{
		"email": "kigali.admin@yopmail.com",
		"path": ("PIU", "Kigali city"),
		"first_name": "Kigali City",
		"last_name": "Admin",
		"gender": "Female",
		"phone": "750000001",
		"position": "Project Administrator",
		"project_role": "Project Administrator",
	},
	{
		"email": "northern.admin@yopmail.com",
		"path": ("PIU", "Northern"),
		"first_name": "Northern",
		"last_name": "Admin",
		"gender": "Male",
		"phone": "750000002",
		"position": "Project Administrator",
		"project_role": "Project Administrator",
	},
	{
		"email": "southern.admin@yopmail.com",
		"path": ("PIU", "Southern"),
		"first_name": "Southern",
		"last_name": "Admin",
		"gender": "Female",
		"phone": "750000003",
		"position": "Project Administrator",
		"project_role": "Project Administrator",
	},
	{
		"email": "eastern.admin@yopmail.com",
		"path": ("PIU", "Eastern"),
		"first_name": "Eastern",
		"last_name": "Admin",
		"gender": "Male",
		"phone": "750000004",
		"position": "Project Administrator",
		"project_role": "Project Administrator",
	},
	{
		"email": "western.admin@yopmail.com",
		"path": ("PIU", "Western"),
		"first_name": "Western",
		"last_name": "Admin",
		"gender": "Female",
		"phone": "750000005",
		"position": "Project Administrator",
		"project_role": "Project Administrator",
	},
	{
		"email": "piu.coordinator@yopmail.com",
		"path": ("PIU",),
		"first_name": "Project",
		"last_name": "Coordinator",
		"gender": "Male",
		"phone": "750000000",
		"position": "Project Coordinator",
		"project_role": "Project Coordinator",
	},
]


def _ensure_level(level_name: str, order: int, changes: list[str], apply: bool) -> str | None:
	"""Return the level-type id for ``level_name``, creating it if absent."""
	existing = frappe.db.get_value(
		"GRM Administrative Level Type",
		{"project": PROJECT, "level_name": level_name},
		"name",
	)
	if existing:
		return existing

	changes.append(f"CREATE level type {level_name} (order {order})")
	if not apply:
		return None

	# Mirrors the PIU/Province rows the original seed created, so the two new
	# levels do not quietly introduce a different SLA regime mid-tree.
	return (
		frappe.get_doc(
			{
				"doctype": "GRM Administrative Level Type",
				"project": PROJECT,
				"level_name": level_name,
				"level_order": order,
				"resolution_days": 30,
				"acknowledgment_days": 7,
				"reminder_before_days": 2,
				"auto_escalate": 1,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _ensure_region(
	region_name: str,
	level_id: str | None,
	parent: str | None,
	level_name: str,
	changes: list[str],
	apply: bool,
) -> str | None:
	"""Return the region id, creating or retagging it as needed.

	A region already present under the right parent but carrying the wrong
	``administrative_level`` is retagged rather than duplicated. That is exactly
	Rwamagana's case, and keeping its id preserves the issues and the user
	assignment that already point at it.
	"""
	existing = frappe.db.get_value(
		"GRM Administrative Region",
		{"project": PROJECT, "region_name": region_name, "parent_region": parent},
		["name", "administrative_level"],
		as_dict=True,
	)
	if existing:
		if level_id and existing.administrative_level != level_id:
			changes.append(f"RETAG region {region_name} -> level {level_name}")
			if apply:
				frappe.db.set_value(
					"GRM Administrative Region", existing.name, "administrative_level", level_id
				)
		return existing.name

	changes.append(f"CREATE region {region_name} ({level_name}) under {parent or '<root>'}")
	if not apply:
		return None

	return (
		frappe.get_doc(
			{
				"doctype": "GRM Administrative Region",
				"project": PROJECT,
				"region_name": region_name,
				"administrative_level": level_id,
				"parent_region": parent,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _build_regions(changes: list[str], apply: bool) -> dict[tuple[str, ...], str]:
	"""Create the four levels and the tree. Returns path tuple -> region id."""
	level_ids = {name: _ensure_level(name, order, changes, apply) for name, order in LEVELS.items()}
	index: dict[tuple[str, ...], str] = {}

	piu = _ensure_region("PIU", level_ids["PIU"], None, "PIU", changes, apply)
	if piu:
		index[("PIU",)] = piu

	for province, districts in TREE.items():
		pid = _ensure_region(province, level_ids["Province"], piu, "Province", changes, apply)
		if pid:
			index[("PIU", province)] = pid
		for district, sectors in districts.items():
			did = _ensure_region(district, level_ids["District"], pid, "District", changes, apply)
			if did:
				index[("PIU", province, district)] = did
			for sector in sectors:
				sid = _ensure_region(sector, level_ids["Sector"], did, "Sector", changes, apply)
				if sid:
					index[("PIU", province, district, sector)] = sid

	return index


def _project_role(role_name: str) -> str | None:
	return frappe.db.get_value("GRM Project Role", {"project": PROJECT, "role_name": role_name}, "name")


def _place_people(index: dict[tuple[str, ...], str], changes: list[str], apply: bool) -> list[str]:
	"""Create any missing User, then point each assignment at the right region.

	Only ``administrative_region`` is touched on an existing assignment. Role,
	duties and activation state are whatever the project already decided; this
	script is about location, and silently re-roling 24 live accounts because a
	spreadsheet column says something different is not its job.
	"""
	unresolved: list[str] = []
	# Sheet order matters: 0782331296 has two rows, and zipping their two
	# regions onto their two assignments oldest-first keeps the pairing stable
	# across re-runs.
	by_email: dict[str, list[dict]] = {}
	for person in PEOPLE:
		by_email.setdefault(person["email"], []).append(person)

	for email, rows in by_email.items():
		regions = []
		for person in rows:
			region = index.get(tuple(person["path"]))
			if region:
				regions.append((region, person))
			else:
				unresolved.append(f"{email} -> {' > '.join(person['path'])}")
		if not regions:
			continue

		if not frappe.db.exists("User", email):
			changes.append(f"CREATE user {email} ({rows[0]['first_name']} {rows[0]['last_name']})")
			if apply:
				# phone_as_username: these are field users who sign in to the
				# mobile app with the phone number the sheet lists, the same
				# way egrm/services/user_import.py creates them from the
				# import wizard. Without it the account exists but nobody can
				# log into it.
				_ensure_user(
					email=email,
					first_name=rows[0]["first_name"],
					last_name=rows[0]["last_name"],
					gender=rows[0]["gender"],
					phone=rows[0]["phone"],
					project_role=_project_role(rows[0]["project_role"]) or "",
					phone_as_username=True,
					mobile_no=rows[0]["phone"],
				)

		assignments = frappe.get_all(
			"GRM User Project Assignment",
			filters={"project": PROJECT, "user": email},
			fields=["name", "administrative_region"],
			order_by="creation",
		)

		for i, (region, person) in enumerate(regions):
			label = " > ".join(person["path"])
			if i < len(assignments):
				if assignments[i].administrative_region == region:
					continue
				changes.append(f"MOVE {email}: -> {label}")
				if apply:
					frappe.db.set_value(
						"GRM User Project Assignment",
						assignments[i].name,
						"administrative_region",
						region,
					)
				continue

			role = _project_role(person["project_role"])
			if not role:
				unresolved.append(f"{email}: no GRM Project Role '{person['project_role']}'")
				continue
			changes.append(f"ASSIGN {email} ({person['project_role']}) -> {label}")
			if apply:
				frappe.get_doc(
					{
						"doctype": "GRM User Project Assignment",
						"user": email,
						"project": PROJECT,
						"role": role,
						"administrative_region": region,
						"position_title": person["position"],
						"is_active": 1,
					}
				).insert(ignore_permissions=True)

	return unresolved


def run(apply: bool = False) -> dict:
	"""Reconcile levels, regions, users and assignments. Returns a report."""
	if not frappe.db.exists("GRM Project", PROJECT):
		raise frappe.ValidationError(f"Project {PROJECT} not found on this site")

	changes: list[str] = []
	index = _build_regions(changes, apply)
	unresolved = _place_people(index, changes, apply)

	repaired, issues, orphans = 0, [], []
	if apply:
		from egrm.egrm.doctype.grm_administrative_region.grm_administrative_region import (
			repair_region_paths,
			validate_region_hierarchy_integrity,
		)

		repaired = repair_region_paths(PROJECT)
		issues = validate_region_hierarchy_integrity(PROJECT)
		# No issue may point at a region that is not in the tree.
		orphans = [
			row.name
			for row in frappe.get_all(
				"GRM Issue", filters={"project": PROJECT}, fields=["name", "administrative_region"]
			)
			if not row.administrative_region
			or not frappe.db.exists("GRM Administrative Region", row.administrative_region)
		]
		frappe.db.commit()

	logger.info("seed_rdap_structure: %s changes, applied=%s", len(changes), apply)
	return {
		"applied": apply,
		"change_count": len(changes),
		"changes": changes,
		"paths_repaired": repaired,
		"integrity_issues": issues,
		"issues_with_dangling_region": orphans,
		"unresolved": unresolved,
	}
