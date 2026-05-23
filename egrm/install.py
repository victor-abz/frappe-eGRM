import frappe

DEFAULT_HOME_PAGE = "grm-portal"
DEFAULT_DESK_APP = "egrm"


def after_install() -> None:
    mark_setup_complete()
    set_default_home_page()
    set_default_desk_app()
    seed_desktop_icons()
    seed_grm_role_catalog()


def seed_grm_role_catalog() -> None:
    """Create the duty/platform Frappe Roles on a fresh install.

    The `seed_grm_role_catalog` patch is the source of truth for these
    role names but only runs via `bench migrate`. Fresh `bench install-app`
    flows initialize the patches table to "all applied" without executing
    the bodies, so the duty Roles never get created — every doctype
    permission row referencing them then references a non-existent Role,
    and downstream contract tests (AC-2.frappe_role_catalog_complete)
    fail. Idempotent.
    """
    from egrm.patches.v16_0.seed_grm_role_catalog import execute as seed_roles
    try:
        seed_roles()
    except Exception as exc:
        frappe.log_error(
            title="seed_grm_role_catalog failed during after_install",
            message=str(exc),
        )


def mark_setup_complete() -> None:
    """Skip Frappe's stock initial-setup wizard.

    Frappe v16's `is_setup_complete()` checks every `Installed Application`
    row's `is_setup_complete` flag; if any are 0, every `/app/*` URL 302s
    to `/desk/setup-wizard/0`. Fresh `bench install-app` lands every row
    at 0, which traps both the AQE Playwright walker (Step 9 wizard URL
    redirects away before the file input renders) and any human admin
    landing on the GRM workspace right after install.

    Mark all installed-app rows complete and clear the request cache so
    `is_setup_complete()` re-reads truth.
    """
    frappe.db.sql(
        "UPDATE `tabInstalled Application` SET is_setup_complete = 1 "
        "WHERE is_setup_complete = 0"
    )
    frappe.db.commit()
    frappe.clear_cache()


def set_default_desk_app() -> None:
    """Pin EGRM as the system-wide default desk app.

    Read by `frappe.apps.get_default_path()` so any logged-in user
    without a per-user `User.default_app` override is routed to
    `/desk/egrm` instead of the empty `/apps` chooser. Idempotent.
    """
    current = frappe.db.get_single_value("System Settings", "default_app")
    if current == DEFAULT_DESK_APP:
        return
    frappe.db.set_single_value("System Settings", "default_app", DEFAULT_DESK_APP)
    frappe.db.commit()


def set_default_home_page() -> None:
    """Point Website Settings at the GRM portal so it renders as the public homepage."""
    try:
        website_settings = frappe.get_single("Website Settings")
    except frappe.DoesNotExistError:
        return

    if website_settings.home_page != DEFAULT_HOME_PAGE:
        website_settings.home_page = DEFAULT_HOME_PAGE
        website_settings.flags.ignore_permissions = True
        website_settings.save()
        frappe.db.commit()


def seed_desktop_icons() -> None:
    """Create v16 Desktop Icon records for the eGRM app and its workspaces.

    On Frappe v16 the Apps screen is driven by the Desktop Icon DocType. The
    framework ships helpers (`create_desktop_icons_from_installed_apps` and
    `create_desktop_icons_from_workspace`) that read `add_to_apps_screen` and
    public Workspace records, but they only run during certain provisioning
    paths. We invoke them on install/migrate so the eGRM tile and its
    workspace shortcuts always land in the Desktop for staff users.
    """
    try:
        from frappe.desk.doctype.desktop_icon.desktop_icon import (
            clear_desktop_icons_cache,
            create_desktop_icons_from_installed_apps,
            create_desktop_icons_from_workspace,
        )
    except ImportError:
        # Older Frappe versions without these helpers — nothing to do.
        return

    # Each helper is wrapped because frappe v16's
    # create_desktop_icons_from_workspace can crash on its internal error path
    # (it calls frappe.error_log(...) which is the doctype list, not a
    # callable). We must NOT let that crash abort the whole migrate, since
    # the rest of the desktop icon work is non-critical.
    try:
        create_desktop_icons_from_installed_apps()
    except Exception as exc:
        frappe.log_error(title="seed_desktop_icons: installed_apps failed", message=str(exc))

    try:
        create_desktop_icons_from_workspace()
    except Exception as exc:
        frappe.log_error(title="seed_desktop_icons: workspace failed", message=str(exc))

    try:
        clear_desktop_icons_cache()
    except Exception:
        pass

    frappe.db.commit()
