frappe.ui.form.on("GRM Project Role", {
    refresh(frm) {
        if (frm.is_new()) return;

        // View issues whose snapshot ``assigned_role`` matches this role.
        // Mirrors the ``View Assigned Issues`` button on GRM Issue Department.
        frm.add_custom_button(__("View Assigned Issues"), function () {
            frappe.set_route("List", "GRM Issue", {
                assigned_role: frm.doc.name,
            });
        });

        // Find categories that route to this role.
        frm.add_custom_button(__("Routed Categories"), function () {
            frappe.set_route("List", "GRM Issue Category", {
                routing_target_type: "Role",
                assigned_role: frm.doc.name,
            });
        });
    },
});
