frappe.ui.form.on('GRM Issue Age Group', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues with this age group
            frm.add_custom_button(__('View Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    citizen_age_group: frm.doc.name
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
                message: __('At least one project must be linked to the age group.')
            });
            validated = false;
        }
        
        // Validate age group format (optional)
        const ageGroupPattern = /^\d+(-\d+)?$/;
        if (frm.doc.age_group && !ageGroupPattern.test(frm.doc.age_group)) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __('Age Group should typically be in the format "18-25" or a single number like "65+".')
            });
        }
    }
});