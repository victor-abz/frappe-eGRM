frappe.ui.form.on("GRM Issue Status", {
	refresh: function (frm) {
		// Add custom buttons
		if (!frm.is_new()) {
			// View issues with this status
			frm.add_custom_button(__("View Issues"), function () {
				frappe.set_route("List", "GRM Issue", {
					status: frm.doc.name,
				});
			});
		}

		// Show warning about unique initial statuses
		if (frm.doc.initial_status) {
			frm.set_intro(
				__(
					"Initial status should be unique for each project. Issues submitted from mobile app will be set to this status."
				),
				"blue"
			);
		}

		// Show info for open status
		if (frm.doc.open_status) {
			frm.set_intro(
				__("Open status allows editing of resolution and assignment details."),
				"blue"
			);
		}

		// Highlight final statuses
		if (frm.doc.final_status) {
			frm.get_field("final_status").$input.css("background-color", "#d9f7be");
		}

		// Highlight rejected statuses
		if (frm.doc.rejected_status) {
			frm.get_field("rejected_status").$input.css("background-color", "#ffccc7");
		}
	},

	validate: function (frm) {
		// Check if there's at least one project linked
		if (!frm.doc.grm_project_link || frm.doc.grm_project_link.length === 0) {
			frappe.msgprint({
				title: __("Validation Error"),
				indicator: "red",
				message: __("At least one project must be linked to the status."),
			});
			validated = false;
		}

		// Ensure only one initial status per project
		if (frm.doc.initial_status) {
			validateUniqueStatusPerProject(frm, "initial_status", "Initial Status");
		}

		// Ensure only one open status per project
		if (frm.doc.open_status) {
			validateUniqueStatusPerProject(frm, "open_status", "Open Status");
		}
	},
});

function validateUniqueStatusPerProject(frm, status_field, status_label) {
	if (frm.doc[status_field] && frm.doc.grm_project_link && frm.doc.grm_project_link.length > 0) {
		let projects = frm.doc.grm_project_link.map((link) => link.project);
		frappe.call({
			method: "frappe.client.get_list",
			args: {
				doctype: "GRM Issue Status",
				filters: {
					[status_field]: 1,
					name: ["!=", frm.doc.name || ""],
				},
				fields: ["name"],
			},
			callback: function (r) {
				if (r.message && r.message.length > 0) {
					// Check if any of these statuses are linked to our projects
					let status_names = r.message.map((s) => s.name);
					frappe.call({
						method: "frappe.client.get_list",
						args: {
							doctype: "GRM Project Link",
							filters: {
								parent: ["in", status_names],
								project: ["in", projects],
							},
							fields: ["parent", "project"],
						},
						callback: function (r2) {
							if (r2.message && r2.message.length > 0) {
								// Group by project
								let project_statuses = {};
								r2.message.forEach((item) => {
									if (!project_statuses[item.project]) {
										project_statuses[item.project] = [];
									}
									project_statuses[item.project].push(item.parent);
								});

								let message =
									__(`The following projects already have ${status_label}:`) +
									"<br>";
								for (let project in project_statuses) {
									message += `- ${project}: ${project_statuses[project].join(
										", "
									)}<br>`;
								}

								frappe.msgprint({
									title: __("Warning"),
									indicator: "orange",
									message: message,
								});
							}
						},
					});
				}
			},
		});
	}
}
