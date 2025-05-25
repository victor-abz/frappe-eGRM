frappe.ui.form.on("GRM User Project Assignment", {
	refresh: function (frm) {
		// Add custom buttons
		if (!frm.is_new()) {
			// View issues assigned to this user
			frm.add_custom_button(__("View Assigned Issues"), function () {
				frappe.set_route("List", "GRM Issue", {
					assignee: frm.doc.user,
					project: frm.doc.project,
				});
			});

			// Add activation buttons based on status
			if (frm.doc.activation_status) {
				add_activation_buttons(frm);
			}
		}

		// Style the activation status indicator
		style_activation_status(frm);
	},

	setup: function (frm) {
		// Set up filters for fields

		// Filter departments based on project
		frm.set_query("department", function () {
			return {
				query: "egrm.server_scripts.queries.get_departments_by_projects",
				filters: {
					projects: [frm.doc.project || ""],
				},
			};
		});

		// Filter administrative_region based on project
		frm.set_query("administrative_region", function () {
			return {
				filters: {
					project: frm.doc.project || "",
				},
			};
		});
	},

	validate: function (frm) {
		// Validate role has correct department/region based on role
		if (frm.doc.role === "GRM Department Head" && !frm.doc.department) {
			frappe.msgprint({
				title: __("Validation Error"),
				indicator: "red",
				message: __("Department Head role requires a department to be specified."),
			});
			validated = false;
		}

		if (frm.doc.role === "GRM Field Officer" && !frm.doc.administrative_region) {
			frappe.msgprint({
				title: __("Validation Error"),
				indicator: "red",
				message: __(
					"Field Officer role requires an administrative region to be specified."
				),
			});
			validated = false;
		}
	},

	role: function (frm) {
		// When role changes, show/hide appropriate fields
		if (frm.doc.role === "GRM Department Head") {
			frm.toggle_reqd("department", true);
			frm.toggle_reqd("administrative_region", false);

			if (!frm.doc.department) {
				frappe.msgprint(__("Please select a department for the Department Head."));
			}
		} else if (frm.doc.role === "GRM Field Officer") {
			frm.toggle_reqd("administrative_region", true);
			frm.toggle_reqd("department", false);

			if (!frm.doc.administrative_region) {
				frappe.msgprint(
					__("Please select an administrative region for the Field Officer.")
				);
			}
		} else {
			frm.toggle_reqd("department", false);
			frm.toggle_reqd("administrative_region", false);
		}
	},

	project: function (frm) {
		// Clear department and region when project changes
		frm.set_value("department", "");
		frm.set_value("administrative_region", "");
	},

	user: function (frm) {
		// Check if user already has assignments to this project
		if (frm.doc.user && frm.doc.project) {
			frappe.call({
				method: "frappe.client.get_list",
				args: {
					doctype: "GRM User Project Assignment",
					filters: {
						user: frm.doc.user,
						project: frm.doc.project,
						name: ["!=", frm.doc.name || ""],
					},
					fields: ["name", "role"],
				},
				callback: function (r) {
					if (r.message && r.message.length > 0) {
						let roles = r.message.map((a) => a.role);
						frappe.msgprint({
							title: __("Warning"),
							indicator: "orange",
							message: __(
								"This user already has the following roles in this project: {0}",
								[roles.join(", ")]
							),
						});
					}
				},
			});
		}
	},

	activation_status: function (frm) {
		// Update styling when status changes
		style_activation_status(frm);
	},
});

// Helper function to add activation buttons
function add_activation_buttons(frm) {
	const status = frm.doc.activation_status;

	// Send Activation Code button (for Draft status)
	if (status === "Draft") {
		frm.add_custom_button(
			__("Send Activation Code"),
			function () {
				frappe.confirm(__("Send activation code to {0}?", [frm.doc.user]), function () {
					frappe.call({
						method: "send_activation_email",
						doc: frm.doc,
						callback: function (r) {
							if (r.message) {
								frappe.msgprint({
									title: __("Success"),
									indicator: "green",
									message: __("Activation code sent successfully!"),
								});
								frm.reload_doc();
							}
						},
					});
				});
			},
			__("Actions")
		);
	}

	// Resend Activation Code button (for Pending/Expired status)
	if (status === "Pending Activation" || status === "Expired") {
		frm.add_custom_button(
			__("Resend Activation Code"),
			function () {
				frappe.confirm(__("Resend activation code to {0}?", [frm.doc.user]), function () {
					frappe.call({
						method: "resend_activation_code",
						doc: frm.doc,
						callback: function (r) {
							if (r.message) {
								frappe.msgprint({
									title: __("Success"),
									indicator: "green",
									message: __("Activation code resent successfully!"),
								});
								frm.reload_doc();
							}
						},
					});
				});
			},
			__("Actions")
		);
	}

	// Manual Activate Worker button (for admins)
	if (status !== "Activated" && frappe.user.has_role(["System Manager", "GRM Administrator"])) {
		frm.add_custom_button(
			__("Manual Activate"),
			function () {
				let d = new frappe.ui.Dialog({
					title: __("Manual Activation"),
					fields: [
						{
							label: __("Activation Code"),
							fieldname: "activation_code",
							fieldtype: "Data",
							reqd: 1,
							description: __(
								"Enter the activation code to manually activate this worker"
							),
						},
						{
							label: __("New Password (Optional)"),
							fieldname: "new_password",
							fieldtype: "Password",
							description: __("Set a new password for the user (optional)"),
						},
					],
					primary_action_label: __("Activate"),
					primary_action(values) {
						frappe.call({
							method: "activate_worker",
							doc: frm.doc,
							args: {
								activation_code: values.activation_code,
								new_password: values.new_password,
							},
							callback: function (r) {
								if (r.message) {
									frappe.msgprint({
										title: __("Success"),
										indicator: "green",
										message: __("Worker activated successfully!"),
									});
									frm.reload_doc();
									d.hide();
								}
							},
						});
					},
				});
				d.show();
			},
			__("Actions")
		);
	}

	// Expire Code button (for admins)
	if (
		status === "Pending Activation" &&
		frappe.user.has_role(["System Manager", "GRM Administrator"])
	) {
		frm.add_custom_button(
			__("Expire Code"),
			function () {
				frappe.confirm(
					__("Mark activation code as expired for {0}?", [frm.doc.user]),
					function () {
						frappe.call({
							method: "expire_activation_code",
							doc: frm.doc,
							callback: function (r) {
								if (r.message) {
									frappe.msgprint({
										title: __("Success"),
										indicator: "orange",
										message: __("Activation code expired successfully!"),
									});
									frm.reload_doc();
								}
							},
						});
					}
				);
			},
			__("Actions")
		);
	}
}

// Helper function to style activation status
function style_activation_status(frm) {
	if (!frm.doc.activation_status) return;

	const status = frm.doc.activation_status;
	const field = frm.get_field("activation_status");

	if (field && field.$wrapper) {
		// Remove existing status classes
		field.$wrapper.removeClass(
			"status-draft status-pending status-activated status-expired status-suspended"
		);

		// Add appropriate status class
		switch (status) {
			case "Draft":
				field.$wrapper.addClass("status-draft");
				break;
			case "Pending Activation":
				field.$wrapper.addClass("status-pending");
				break;
			case "Activated":
				field.$wrapper.addClass("status-activated");
				break;
			case "Expired":
				field.$wrapper.addClass("status-expired");
				break;
			case "Suspended":
				field.$wrapper.addClass("status-suspended");
				break;
		}
	}
}

// List view customizations
frappe.listview_settings["GRM User Project Assignment"] = {
	onload: function (listview) {
		// Add Export Activation Codes button for admins
		if (frappe.user.has_role(["System Manager", "GRM Administrator", "GRM Project Manager"])) {
			listview.page.add_inner_button(__("Export Activation Codes"), function () {
				let d = new frappe.ui.Dialog({
					title: __("Export Activation Codes"),
					fields: [
						{
							label: __("Project"),
							fieldname: "project",
							fieldtype: "Link",
							options: "GRM Project",
							reqd: 1,
							description: __("Select project to export activation codes for"),
						},
					],
					primary_action_label: __("Export CSV"),
					primary_action(values) {
						window.open(
							"/api/method/egrm.egrm.doctype.grm_user_project_assignment.grm_user_project_assignment.export_project_activation_codes?project_code=" +
								encodeURIComponent(values.project)
						);
						d.hide();
					},
				});
				d.show();
			});
		}
	},

	get_indicator: function (doc) {
		// Add status indicators in list view
		if (doc.activation_status) {
			switch (doc.activation_status) {
				case "Draft":
					return [__("Draft"), "grey", "activation_status,=,Draft"];
				case "Pending Activation":
					return [__("Pending"), "orange", "activation_status,=,Pending Activation"];
				case "Activated":
					return [__("Activated"), "green", "activation_status,=,Activated"];
				case "Expired":
					return [__("Expired"), "red", "activation_status,=,Expired"];
				case "Suspended":
					return [__("Suspended"), "darkgrey", "activation_status,=,Suspended"];
			}
		}

		// Fallback to active status
		if (doc.is_active) {
			return [__("Active"), "green", "is_active,=,1"];
		} else {
			return [__("Inactive"), "grey", "is_active,=,0"];
		}
	},
};
