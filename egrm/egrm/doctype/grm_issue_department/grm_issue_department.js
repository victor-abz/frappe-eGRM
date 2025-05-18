frappe.ui.form.on('GRM Issue Department', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues assigned to this department
            frm.add_custom_button(__('View Assigned Issues'), function() {
                // Find categories assigned to this department first
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'GRM Issue Category',
                        filters: {
                            assigned_department: frm.doc.name
                        },
                        fields: ['name']
                    },
                    callback: function(r) {
                        if (r.message && r.message.length > 0) {
                            let categories = r.message.map(c => c.name);
                            frappe.set_route('List', 'GRM Issue', {
                                category: ['in', categories]
                            });
                        } else {
                            frappe.msgprint(__('No categories are assigned to this department.'));
                        }
                    }
                });
            });
            
            // View department members
            frm.add_custom_button(__('View Department Members'), function() {
                frappe.set_route('List', 'GRM User Project Assignment', {
                    department: frm.doc.name
                });
            });
        }
    },
    
    setup: function(frm) {
        // Filter for head field
        frm.set_query('head', function() {
            return {
                filters: {
                    'ignore_user_type': 1
                }
            };
        });
    },
    
    validate: function(frm) {
        // Ensure there's at least one project linked
        if (!frm.doc.grm_project_link || frm.doc.grm_project_link.length === 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('At least one project must be linked to the department.')
            });
            validated = false;
        }
    }
});