frappe.ui.form.on('GRM Administrative Level Type', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Regions'), function() {
                frappe.set_route('List', 'GRM Administrative Region', {
                    administrative_level: frm.doc.name
                });
            });
        }
    },
    
    validate: function(frm) {
        // Validate level order is positive
        if (frm.doc.level_order < 0) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Level Order cannot be negative.')
            });
            validated = false;
        }
    },
    
    project: function(frm) {
        // Check if there are already levels for this project
        if (frm.doc.project) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'GRM Administrative Level Type',
                    filters: {
                        project: frm.doc.project
                    },
                    fields: ['level_name', 'level_order'],
                    order_by: 'level_order ASC'
                },
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        let levelsHtml = '<b>Existing levels for this project:</b><br>';
                        r.message.forEach(function(level) {
                            levelsHtml += `${level.level_name} (Order: ${level.level_order})<br>`;
                        });
                        
                        // Show existing levels as a helpful reference
                        frm.set_df_property('level_order', 'description', levelsHtml);
                        frm.refresh_field('level_order');
                    }
                }
            });
        }
    }
});