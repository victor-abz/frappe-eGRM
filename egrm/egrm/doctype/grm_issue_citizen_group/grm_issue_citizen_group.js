frappe.ui.form.on('GRM Issue Citizen Group', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues with this citizen group
            frm.add_custom_button(__('View Issues (Primary)'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    citizen_group_1: frm.doc.name
                });
            });
            
            frm.add_custom_button(__('View Issues (Secondary)'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    citizen_group_2: frm.doc.name
                });
            });
        }
        
        // Add helpers for group type
        if (frm.doc.group_type === "1") {
            frm.set_intro(__('Primary groups are used for the main citizen classification.'), 'blue');
        } else if (frm.doc.group_type === "2") {
            frm.set_intro(__('Secondary groups are used for additional citizen classification.'), 'blue');
        }
    },
    
    validate: function(frm) {
        // Check if there's at least one project linked
        if (!frm.doc.grm_project_link || frm.doc.grm_project_link.length === 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('At least one project must be linked to the citizen group.')
            });
            validated = false;
        }
    }
});