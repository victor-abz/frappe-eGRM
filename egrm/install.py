import frappe

DEFAULT_HOME_PAGE = "grm-portal"


def after_install() -> None:
    set_default_home_page()
    seed_desktop_icons()


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

    create_desktop_icons_from_installed_apps()
    create_desktop_icons_from_workspace()
    clear_desktop_icons_cache()
    frappe.db.commit()
