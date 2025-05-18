frappe.ui.form.on('GRM Administrative Region', {
    refresh: function(frm) {
        // Add custom buttons
        if (!frm.is_new()) {
            // View child regions
            frm.add_custom_button(__('View Child Regions'), function() {
                frappe.set_route('List', 'GRM Administrative Region', {
                    parent_region: frm.doc.name
                });
            });
            
            // View issues in this region
            frm.add_custom_button(__('View Issues'), function() {
                frappe.set_route('List', 'GRM Issue', {
                    administrative_region: frm.doc.name
                });
            });
            
            // Show map if coordinates exist
            if (frm.doc.latitude && frm.doc.longitude) {
                frm.add_custom_button(__('View on Map'), function() {
                    // Open Google Maps with the coordinates
                    window.open(`https://www.google.com/maps/search/?api=1&query=${frm.doc.latitude},${frm.doc.longitude}`, '_blank');
                });
            }
        }
        
        // Add a map section if coordinates exist
        if (frm.doc.latitude && frm.doc.longitude) {
            // Create a simple map visualization using HTML
            frm.add_web_link(`https://www.google.com/maps/search/?api=1&query=${frm.doc.latitude},${frm.doc.longitude}`, __('View Location on Google Maps'));
        }
    },
    
    setup: function(frm) {
        // Filter parent region based on project and prevent circular references
        frm.set_query('parent_region', function() {
            return {
                filters: {
                    'project': frm.doc.project || '',
                    'name': ['!=', frm.doc.name || '']
                }
            };
        });
        
        // Filter administrative level based on project
        frm.set_query('administrative_level', function() {
            return {
                filters: {
                    'project': frm.doc.project || ''
                }
            };
        });
    },
    
    validate: function(frm) {
        // Validate coordinates
        if (frm.doc.latitude && (frm.doc.latitude < -90 || frm.doc.latitude > 90)) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Latitude must be between -90 and 90.')
            });
            validated = false;
        }
        
        if (frm.doc.longitude && (frm.doc.longitude < -180 || frm.doc.longitude > 180)) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('Longitude must be between -180 and 180.')
            });
            validated = false;
        }
    },
    
    project: function(frm) {
        // Clear parent region and administrative level when project changes
        frm.set_value('parent_region', '');
        frm.set_value('administrative_level', '');
    },
    
    administrative_level: function(frm) {
        // When administrative level changes, suggest appropriate parent regions
        if (frm.doc.administrative_level && frm.doc.project) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'GRM Administrative Level Type',
                    filters: {
                        name: frm.doc.administrative_level
                    },
                    fieldname: 'level_order'
                },
                callback: function(r) {
                    if (r.message && r.message.level_order > 1) {
                        // Get potential parent levels
                        frappe.call({
                            method: 'frappe.client.get_list',
                            args: {
                                doctype: 'GRM Administrative Level Type',
                                filters: {
                                    project: frm.doc.project,
                                    level_order: ['<', r.message.level_order]
                                },
                                fields: ['name'],
                                order_by: 'level_order DESC',
                                limit: 1
                            },
                            callback: function(r2) {
                                if (r2.message && r2.message.length > 0) {
                                    // Suggest setting a parent region
                                    frappe.msgprint(__('Please select a parent region from the administrative level above.'), __('Suggestion'));
                                }
                            }
                        });
                    }
                }
            });
        }
    }
});