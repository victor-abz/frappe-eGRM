frappe.ui.form.on('GRM Project', {
    refresh: function(frm) {
        // Add custom buttons
        if (frm.doc.docstatus !== 2) { // Not cancelled
            frm.add_custom_button(__('View Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {project: frm.doc.name});
            }, __('Actions'));
            
            frm.add_custom_button(__('Create Issue'), function() {
                frappe.new_doc('GRM Issue', {
                    project: frm.doc.name
                });
            }, __('Actions'));
        }
        
        // Add a dashboard to show key metrics
        if (!frm.is_new()) {
            frm.dashboard.add_section(
                frappe.render_template('grm_project_dashboard', {
                    data: {}
                })
            );
            
            // Load statistics
            frappe.call({
                method: 'frappe.client.get_count',
                args: {
                    doctype: 'GRM Issue',
                    filters: {
                        project: frm.doc.name
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        $(frm.dashboard.wrapper).find('.total-issues').text(r.message);
                    }
                }
            });
            
            frappe.call({
                method: 'frappe.client.get_count',
                args: {
                    doctype: 'GRM Issue',
                    filters: {
                        project: frm.doc.name,
                        status: ['in', frm.doc.__onload?.open_statuses || []]
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        $(frm.dashboard.wrapper).find('.open-issues').text(r.message);
                    }
                }
            });
        }
    },
    
    setup: function(frm) {
        // Load open statuses
        if (!frm.is_new()) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'GRM Issue Status',
                    fields: ['name'],
                    filters: {
                        open_status: 1
                    }
                },
                callback: function(r) {
                    if (r.message) {
                        frm.doc.__onload = frm.doc.__onload || {};
                        frm.doc.__onload.open_statuses = r.message.map(d => d.name);
                    }
                }
            });
        }
    },
    
    validate: function(frm) {
        // Check if project code has special characters
        if (frm.doc.project_code && /[^A-Za-z0-9_-]/.test(frm.doc.project_code)) {
            frappe.msgprint({
                title: __('Warning'),
                indicator: 'orange',
                message: __('Project Code should only contain alphanumeric characters, underscores, and hyphens for best compatibility.')
            });
        }
    },
    
    start_date: function(frm) {
        // Update end date if it's before start date
        if (frm.doc.start_date && frm.doc.end_date && frm.doc.start_date > frm.doc.end_date) {
            frm.set_value('end_date', '');
            frappe.msgprint(__('End Date cannot be before Start Date'));
        }
    },
    
    end_date: function(frm) {
        // Update end date if it's before start date
        if (frm.doc.start_date && frm.doc.end_date && frm.doc.start_date > frm.doc.end_date) {
            frm.set_value('end_date', '');
            frappe.msgprint(__('End Date cannot be before Start Date'));
        }
    }
});

frappe.templates['grm_project_dashboard'] = `
<div class="row">
    <div class="col-sm-4">
        <div class="stat-box">
            <div class="stat-value total-issues">--</div>
            <div class="stat-label">Total Issues</div>
        </div>
    </div>
    <div class="col-sm-4">
        <div class="stat-box">
            <div class="stat-value open-issues">--</div>
            <div class="stat-label">Open Issues</div>
        </div>
    </div>
</div>
`;