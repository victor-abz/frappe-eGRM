import frappe

DEFAULT_HOME_PAGE = "grm-portal"


def after_install() -> None:
    set_default_home_page()


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
