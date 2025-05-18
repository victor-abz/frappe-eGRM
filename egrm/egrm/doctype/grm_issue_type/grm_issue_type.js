frappe.ui.form.on('GRM Issue Type', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues of this type
            frm.add_custom_button(__('View Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    issue_type: frm.doc.name
                });
            });
        }
    },
    
    validate: function(frm) {
        // Check if there's at least one project linked
        if (!frm.doc.grm_project_link || frm.doc.grm_project_link.length === 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('At least one project must be linked to the issue type.')
            });
            validated = false;
        }
    }
});