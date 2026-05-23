// Project Setup Wizard — page entrypoint.
//
// The wizard's helpers and per-step classes live in
// ``egrm/public/js/grm_project_wizard/*.js`` and are concatenated onto this
// page's script via the ``page_js`` hook in ``hooks.py``. Keep this file
// minimal: framework wiring only, no business logic.
frappe.pages["grm-project-wizard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("Project Setup Wizard"),
        single_column: true,
    });
    new GRMProjectWizard(page);
};
