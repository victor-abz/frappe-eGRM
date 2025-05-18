frappe.ui.form.on('GRM Issue Category', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View issues in this category
            frm.add_custom_button(__('View Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    category: frm.doc.name
                });
            });
            
            // Show statistics
            if (frm.doc.__onload && frm.doc.__onload.stats) {
                let stats = frm.doc.__onload.stats;
                let html = `
                    <div class="row">
                        <div class="col-sm-4">
                            <div class="stat-box">
                                <div class="stat-value">${stats.total || 0}</div>
                                <div class="stat-label">Total Issues</div>
                            </div>
                        </div>
                        <div class="col-sm-4">
                            <div class="stat-box">
                                <div class="stat-value">${stats.open || 0}</div>
                                <div class="stat-label">Open Issues</div>
                            </div>
                        </div>
                        <div class="col-sm-4">
                            <div class="stat-box">
                                <div class="stat-value">${stats.avg_resolution_days || '--'}</div>
                                <div class="stat-label">Avg. Resolution Days</div>
                            </div>
                        </div>
                    </div>
                `;
                frm.dashboard.add_section(html);
                frm.dashboard.show();
            }
        }
    },
    
    setup: function(frm) {
        // Filter department fields based on project links
        frm.set_query('assigned_department', function() {
            let projects = [];
            if (frm.doc.grm_project_link) {
                projects = frm.doc.grm_project_link.map(d => d.project);
            }
            
            return {
                query: 'egrm.server_scripts.queries.get_departments_by_projects',
                filters: {
                    'projects': projects
                }
            };
        });
        
        frm.set_query('assigned_appeal_department', function() {
            let projects = [];
            if (frm.doc.grm_project_link) {
                projects = frm.doc.grm_project_link.map(d => d.project);
            }
            
            return {
                query: 'egrm.server_scripts.queries.get_departments_by_projects',
                filters: {
                    'projects': projects
                }
            };
        });
        
        frm.set_query('assigned_escalation_department', function() {
            let projects = [];
            if (frm.doc.grm_project_link) {
                projects = frm.doc.grm_project_link.map(d => d.project);
            }
            
            return {
                query: 'egrm.server_scripts.queries.get_departments_by_projects',
                filters: {
                    'projects': projects
                }
            };
        });
        
        // Filter administrative level based on project
        frm.set_query('administrative_level', function() {
            let projects = [];
            if (frm.doc.grm_project_link) {
                projects = frm.doc.grm_project_link.map(d => d.project);
            }
            
            if (projects.length === 1) {
                return {
                    filters: {
                        'project': projects[0]
                    }
                };
            } else if (projects.length > 1) {
                return {
                    filters: {
                        'project': ['in', projects]
                    }
                };
            }
            
            return {};
        });
        
        // Load statistics for existing categories
        if (!frm.is_new()) {
            frappe.call({
                method: 'egrm.server_scripts.queries.get_category_stats',
                args: {
                    category: frm.doc.name
                },
                callback: function(r) {
                    if (r.message) {
                        frm.doc.__onload = frm.doc.__onload || {};
                        frm.doc.__onload.stats = r.message;
                        frm.refresh();
                    }
                }
            });
        }
    },
    
    validate: function(frm) {
        // Check if there's at least one project linked
        if (!frm.doc.grm_project_link || frm.doc.grm_project_link.length === 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('At least one project must be linked to the category.')
            });
            validated = false;
        }
        
        // Check if abbreviation is provided
        if (!frm.doc.abbreviation) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Abbreviation is required for internal code generation.')
            });
            validated = false;
        } else if (frm.doc.abbreviation.length > 5) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __('Abbreviation should be short (5 characters or less) for better code readability.')
            });
        }
    }
});