frappe.ui.form.on('GRM User Project Assignment', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues assigned to this user
            frm.add_custom_button(__('View Assigned Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    assignee: frm.doc.user,
                    project: frm.doc.project
                });
            });
        }
    },
    
    setup: function(frm) {
        // Set up filters for fields
        
        // Filter departments based on project
        frm.set_query('department', function() {
            return {
                query: 'egrm.server_scripts.queries.get_departments_by_projects',
                filters: {
                    'projects': [frm.doc.project || '']
                }
            };
        });
        
        // Filter administrative_region based on project
        frm.set_query('administrative_region', function() {
            return {
                filters: {
                    'project': frm.doc.project || ''
                }
            };
        });
    },
    
    validate: function(frm) {
        // Validate role has correct department/region based on role
        if (frm.doc.role === "GRM Department Head" && !frm.doc.department) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Department Head role requires a department to be specified.')
            });
            validated = false;
        }
        
        if (frm.doc.role === "GRM Field Officer" && !frm.doc.administrative_region) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Field Officer role requires an administrative region to be specified.')
            });
            validated = false;
        }
    },
    
    role: function(frm) {
        // When role changes, show/hide appropriate fields
        if (frm.doc.role === "GRM Department Head") {
            frm.toggle_reqd('department', true);
            frm.toggle_reqd('administrative_region', false);
            
            if (!frm.doc.department) {
                frappe.msgprint(__('Please select a department for the Department Head.'));
            }
        } else if (frm.doc.role === "GRM Field Officer") {
            frm.toggle_reqd('administrative_region', true);
            frm.toggle_reqd('department', false);
            
            if (!frm.doc.administrative_region) {
                frappe.msgprint(__('Please select an administrative region for the Field Officer.'));
            }
        } else {
            frm.toggle_reqd('department', false);
            frm.toggle_reqd('administrative_region', false);
        }
    },
    
    project: function(frm) {
        // Clear department and region when project changes
        frm.set_value('department', '');
        frm.set_value('administrative_region', '');
    },
    
    user: function(frm) {
        // Check if user already has assignments to this project
        if (frm.doc.user && frm.doc.project) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'GRM User Project Assignment',
                    filters: {
                        user: frm.doc.user,
                        project: frm.doc.project,
                        name: ['!=', frm.doc.name || '']
                    },
                    fields: ['name', 'role']
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        let roles = r.message.map(a => a.role);
                        frappe.msgprint({
                            title: __('Warning'),
                            indicator: 'orange',
                            message: __('This user already has the following roles in this project: {0}', [roles.join(', ')])
                        });
                    }
                }
            });
        }
    }
});