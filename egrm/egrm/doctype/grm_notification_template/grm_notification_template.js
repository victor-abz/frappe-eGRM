// Copyright (c) 2025, eGRM and contributors
// For license information, please see license.txt

frappe.ui.form.on('GRM Notification Template', {
	refresh: function(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__('Preview'), function() {
				let d = new frappe.ui.Dialog({
					title: __('Template Preview'),
					fields: [
						{
							fieldname: 'html',
							fieldtype: 'HTML',
							options: '<p>Preview with sample data:</p><ul><li><strong>Tracking Code:</strong> GRM-2025-001</li><li><strong>Status:</strong> Open</li><li><strong>Subject:</strong> Road Damage Complaint</li></ul>'
						}
					]
				});
				d.show();
			});
		}
	},

	enable_sms: function(frm) {
		frm.toggle_reqd('sms_message', frm.doc.enable_sms);
	}
});
