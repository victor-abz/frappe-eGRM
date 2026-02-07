frappe.ui.form.on("GRM Issue", {
	// Helper functions for button enablement logic

	/**
	 * Check if current user is assigned to the issue
	 */
	_isIssueAssignedToMe: function (frm) {
		if (!frm.doc.assignee) return false;
		const currentUser = frappe.session.user;
		return (
			frm.doc.assignee === currentUser ||
			(frm.doc.reporter === currentUser && frm.doc.assignee === currentUser)
		);
	},

	/**
	 * Check if Accept button should be enabled
	 */
	_isAcceptEnabled: function (frm) {
		const currentUser = frappe.session.user;
		const isAssigned = frm.events._isIssueAssignedToMe(frm);

		// Check for unknown status (empty or null status)
		const hasUnknownStatus = !frm.doc.status || frm.doc.status === "";
		if (hasUnknownStatus && isAssigned) {
			return { enabled: true, reason: "Issue has unknown status and user is assigned" };
		}

		// Check for initial status
		if (frm.doc.status && frm.doc.__onload?.status_info?.initial_status && isAssigned) {
			return { enabled: true, reason: "Issue has initial status and user is assigned" };
		}

		// Determine reason for being disabled
		let reason = "";
		if (!isAssigned) {
			reason = "User is not assigned to this issue";
		} else if (!hasUnknownStatus && !frm.doc.__onload?.status_info?.initial_status) {
			reason = "Issue is not in initial status or unknown status";
		}

		return { enabled: false, reason: reason };
	},

	/**
	 * Check if Record Resolution actions should be enabled
	 */
	_isRecordResolutionEnabled: function (frm) {
		const isAssigned = frm.events._isIssueAssignedToMe(frm);
		const isOpenStatus = frm.doc.__onload?.status_info?.open_status;
		const isNotEscalated = !frm.doc.escalate_flag;

		if (isOpenStatus && isAssigned && isNotEscalated) {
			return {
				enabled: true,
				reason: "Issue has open status, user is assigned, and not escalated",
			};
		}

		// Determine reason for being disabled
		let reason = "";
		if (!isAssigned) {
			reason = "User is not assigned to this issue";
		} else if (!isOpenStatus) {
			reason = "Issue is not in open status";
		} else if (frm.doc.escalate_flag) {
			reason = "Issue has been escalated";
		}

		return { enabled: false, reason: reason };
	},

	/**
	 * Check if Rate/Appeal button should be enabled
	 */
	_isRateAppealEnabled: function (frm) {
		const isNotAssigned = !frm.events._isIssueAssignedToMe(frm);
		const isFinalStatus = frm.doc.__onload?.status_info?.final_status;

		if (isFinalStatus && isNotAssigned) {
			return { enabled: true, reason: "Issue has final status and user is not assigned" };
		}

		// Determine reason for being disabled
		let reason = "";
		if (!isFinalStatus) {
			reason = "Issue is not in final status";
		} else if (!isNotAssigned) {
			reason = "User is assigned to this issue (only non-assigned users can rate/appeal)";
		}

		return { enabled: false, reason: reason };
	},

	/**
	 * Check if Escalate button should be enabled
	 */
	_isEscalateEnabled: function (frm) {
		const recordResolutionResult = frm.events._isRecordResolutionEnabled(frm);
		const isNotEscalated = !frm.doc.escalate_flag;

		if (recordResolutionResult.enabled && isNotEscalated) {
			return { enabled: true, reason: "Can record resolution and issue is not escalated" };
		}

		// Determine reason for being disabled
		let reason = "";
		if (!recordResolutionResult.enabled) {
			reason = `Cannot record resolution: ${recordResolutionResult.reason}`;
		} else if (frm.doc.escalate_flag) {
			reason = "Issue has already been escalated";
		}

		return { enabled: false, reason: reason };
	},

	/**
	 * Check if Reject button should be enabled
	 */
	_isRejectEnabled: function (frm) {
		const acceptResult = frm.events._isAcceptEnabled(frm);
		return {
			enabled: acceptResult.enabled,
			reason: acceptResult.reason + " (same conditions as Accept)",
		};
	},

	/**
	 * Check if Reassign button should be enabled
	 */
	_isReassignEnabled: function (frm) {
		// Only allow reassignment if user has project access or is assigned
		const isAssigned = frm.events._isIssueAssignedToMe(frm);
		const hasProjectAccess = frm.doc.project; // Basic check - user can see the document

		if (isAssigned || hasProjectAccess) {
			const reason = isAssigned ? "User is assigned to issue" : "User has project access";
			return { enabled: true, reason: reason };
		}

		return { enabled: false, reason: "User is not assigned and has no project access" };
	},

	/**
	 * Check if Record Steps Taken button should be enabled
	 */
	_isAddCommentEnabled: function (frm) {
		// Record steps should only be available when issue is in progress (same as Record Resolution)
		const recordResolutionResult = frm.events._isRecordResolutionEnabled(frm);
		return {
			enabled: recordResolutionResult.enabled,
			reason: recordResolutionResult.reason + " (same conditions as Record Resolution)",
		};
	},

	/**
	 * Add standardized comment and log entry
	 */
	_addCommentAndLog: function (frm, commentText, logText, actionType) {
		// Add comment
		const comment = frm.add_child("grm_issue_comment");
		comment.user = frappe.session.user;
		comment.comment = commentText;

		// Add log entry
		const log = frm.add_child("grm_issue_log");
		log.user = frappe.session.user;
		log.text = logText;
		log.timestamp = frappe.datetime.now_datetime();

		// Add action tracking fields if available
		if (actionType) {
			log.action_taken = actionType;
			log.action_taken_by = frappe.session.user;
			log.action_taken_date = frappe.datetime.now_datetime();
		}
	},

	/**
	 * Accept Issue Action
	 */
	_acceptIssue: function (frm) {
		frappe.confirm(__("Are you sure you want to accept this issue?"), function () {
			frappe.call({
				method: "egrm.server_scripts.issue_actions.accept_issue",
				args: {
					issue: frm.doc.name,
				},
				callback: function (r) {
					if (r.message) {
						frm.reload_doc();
						frappe.show_alert({
							message: __("Issue accepted successfully"),
							indicator: "green",
						});
					}
				},
			});
		});
	},

	/**
	 * Reject Issue Action
	 */
	_rejectIssue: function (frm) {
		frappe.prompt(
			{
				fieldname: "reason",
				label: __("Rejection Reason"),
				fieldtype: "Text",
				reqd: 1,
			},
			function (values) {
				frappe.call({
					method: "egrm.server_scripts.issue_actions.reject_issue",
					args: {
						issue: frm.doc.name,
						reason: values.reason,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Issue rejected successfully"),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Reject Issue"),
			__("Reject")
		);
	},

	/**
	 * Record Steps Action
	 */
	_recordSteps: function (frm) {
		frappe.prompt(
			{
				fieldname: "steps",
				label: __("Steps Taken"),
				fieldtype: "Text",
				reqd: 1,
			},
			function (values) {
				frappe.call({
					method: "egrm.server_scripts.issue_actions.record_steps",
					args: {
						issue: frm.doc.name,
						steps: values.steps,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Steps recorded successfully"),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Record Steps"),
			__("Record")
		);
	},

	/**
	 * Record Resolution Action
	 */
	_recordResolution: function (frm) {
		frappe.prompt(
			{
				fieldname: "resolution",
				label: __("Resolution Details"),
				fieldtype: "Text",
				reqd: 1,
			},
			function (values) {
				frappe.call({
					method: "egrm.server_scripts.issue_actions.record_resolution",
					args: {
						issue: frm.doc.name,
						resolution: values.resolution,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Resolution recorded successfully"),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Record Resolution"),
			__("Resolve")
		);
	},

	/**
	 * Escalate Issue Action
	 */
	_escalateIssue: function (frm) {
		frappe.prompt(
			[
				{
					fieldname: "reason",
					label: __("Escalation Reason"),
					fieldtype: "Text",
					reqd: 1,
				},
				{
					fieldname: "due_at",
					label: __("Due Date"),
					fieldtype: "Datetime",
					reqd: 1,
				},
			],
			function (values) {
				frappe.call({
					method: "egrm.server_scripts.issue_actions.escalate_issue",
					args: {
						issue: frm.doc.name,
						reason: values.reason,
						due_at: values.due_at,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Issue escalated successfully"),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Escalate Issue"),
			__("Escalate")
		);
	},

	/**
	 * Rate/Appeal Issue Action
	 */
	_rateAppealIssue: function (frm) {
		const hasRating = frm.doc.rating && frm.doc.rating > 0;
		const hasAppeal = frm.doc.appeal_submitted;

		let fields = [];

		if (!hasRating) {
			fields.push({
				fieldname: "action_type",
				label: __("Action"),
				fieldtype: "Select",
				options: "Rate Issue\nSubmit Appeal",
				reqd: 1,
			});
		} else if (!hasAppeal) {
			fields.push({
				fieldname: "action_type",
				label: __("Action"),
				fieldtype: "Select",
				options: "Submit Appeal",
				reqd: 1,
				default: "Submit Appeal",
			});
		}

		if (fields.length === 0) {
			frappe.msgprint(__("No actions available"));
			return;
		}

		fields.push({
			fieldname: "rating",
			label: __("Rating (1-5)"),
			fieldtype: "Select",
			options: "1\n2\n3\n4\n5",
			depends_on: "eval:doc.action_type === 'Rate Issue'",
		});

		fields.push({
			fieldname: "comment",
			label: __("Comment"),
			fieldtype: "Text",
			reqd: 1,
		});

		frappe.prompt(
			fields,
			function (values) {
				const method =
					values.action_type === "Rate Issue"
						? "egrm.server_scripts.issue_actions.rate_issue"
						: "egrm.server_scripts.issue_actions.appeal_issue";

				frappe.call({
					method: method,
					args: {
						issue: frm.doc.name,
						rating: values.rating || null,
						comment: values.comment,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							const message =
								values.action_type === "Rate Issue"
									? __("Rating submitted successfully")
									: __("Appeal submitted successfully");
							frappe.show_alert({
								message: message,
								indicator: "green",
							});
						}
					},
				});
			},
			__("Rate/Appeal Issue"),
			__("Submit")
		);
	},

	/**
	 * Debug function to log button enablement status
	 */
	_debugButtonStatus: function (frm) {
		if (frm.doc.docstatus !== 1) {
			console.log("Debug: Document not submitted, no action buttons");
			return;
		}

		console.log("=== Button Status Debug ===");
		console.log("Current user:", frappe.session.user);
		console.log("User roles:", frappe.user_roles);
		console.log("Assignee:", frm.doc.assignee);
		console.log("Status:", frm.doc.status);
		console.log("Status info:", frm.doc.__onload?.status_info);
		console.log("Escalate flag:", frm.doc.escalate_flag);
		console.log("Project:", frm.doc.project);

		console.log("Button enablement with reasons:");
		const acceptResult = frm.events._isAcceptEnabled(frm);
		console.log("- Accept enabled:", acceptResult.enabled, "- Reason:", acceptResult.reason);

		const rejectResult = frm.events._isRejectEnabled(frm);
		console.log("- Reject enabled:", rejectResult.enabled, "- Reason:", rejectResult.reason);

		const recordResolutionResult = frm.events._isRecordResolutionEnabled(frm);
		console.log(
			"- Record Resolution enabled:",
			recordResolutionResult.enabled,
			"- Reason:",
			recordResolutionResult.reason
		);

		const escalateResult = frm.events._isEscalateEnabled(frm);
		console.log(
			"- Escalate enabled:",
			escalateResult.enabled,
			"- Reason:",
			escalateResult.reason
		);

		const rateAppealResult = frm.events._isRateAppealEnabled(frm);
		console.log(
			"- Rate/Appeal enabled:",
			rateAppealResult.enabled,
			"- Reason:",
			rateAppealResult.reason
		);

		const reassignResult = frm.events._isReassignEnabled(frm);
		console.log(
			"- Reassign enabled:",
			reassignResult.enabled,
			"- Reason:",
			reassignResult.reason
		);

		const recordStepsResult = frm.events._isAddCommentEnabled(frm);
		console.log(
			"- Record Steps Taken enabled:",
			recordStepsResult.enabled,
			"- Reason:",
			recordStepsResult.reason
		);

		console.log("========================");
	},

	/**
	 * Add all action buttons based on current state
	 */
	_addActionButtons: function (frm) {
		// Clear existing custom buttons
		frm.clear_custom_buttons();

		if (frm.doc.docstatus !== 1) return; // Only for submitted documents

		// Accept/Reject buttons
		const acceptResult = frm.events._isAcceptEnabled(frm);
		if (acceptResult.enabled) {
			frm.add_custom_button(
				__("Accept Issue"),
				() => {
					frm.events._acceptIssue(frm);
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Reject Issue"),
				() => {
					frm.events._rejectIssue(frm);
				},
				__("Actions")
			);
		}

		// Record Resolution buttons
		const recordResolutionResult = frm.events._isRecordResolutionEnabled(frm);
		if (recordResolutionResult.enabled) {
			frm.add_custom_button(
				__("Record Steps"),
				() => {
					frm.events._recordSteps(frm);
				},
				__("Actions")
			);

			frm.add_custom_button(
				__("Record Resolution"),
				() => {
					frm.events._recordResolution(frm);
				},
				__("Actions")
			);
		}

		// Escalate button
		const escalateResult = frm.events._isEscalateEnabled(frm);
		if (escalateResult.enabled) {
			frm.add_custom_button(
				__("Escalate Issue"),
				() => {
					frm.events._escalateIssue(frm);
				},
				__("Actions")
			);
		}

		// Rate/Appeal button
		const rateAppealResult = frm.events._isRateAppealEnabled(frm);
		if (rateAppealResult.enabled) {
			frm.add_custom_button(
				__("Rate/Appeal Issue"),
				() => {
					frm.events._rateAppealIssue(frm);
				},
				__("Actions")
			);
		}

		// Record Steps Taken button (only for issues in progress - same as Record Resolution)
		const recordStepsResult = frm.events._isAddCommentEnabled(frm);
		if (recordStepsResult.enabled) {
			frm.add_custom_button(
				__("Record Steps Taken"),
				() => {
					frm.events._addComment(frm);
				},
				__("Actions")
			);
		}

		// Reassign button as separate button (only if enabled)
		const reassignResult = frm.events._isReassignEnabled(frm);
		if (reassignResult.enabled) {
			frm.add_custom_button(__("Reassign Issue"), () => {
				frm.events._reassignIssue(frm);
			});
		}

		// Debug button (only for Administrators)
		if (frappe.user_roles.includes("Administrator")) {
			frm.add_custom_button(
				__("Debug Button Status"),
				() => {
					frm.events._debugButtonStatus(frm);
				},
				__("Debug")
			);
		}
	},

	/**
	 * Reassign Issue Action
	 */
	_reassignIssue: function (frm) {
		frappe.prompt(
			[
				{
					fieldname: "assignee",
					label: __("New Assignee"),
					fieldtype: "Link",
					options: "User",
					reqd: 1,
					get_query: function () {
						return {
							query: "egrm.server_scripts.queries.get_project_users",
							filters: {
								project: frm.doc.project,
							},
						};
					},
				},
				{
					fieldname: "comment",
					label: __("Reason"),
					fieldtype: "Text",
					reqd: 1,
				},
			],
			function (values) {
				frappe.call({
					method: "egrm.server_scripts.issue_actions.reassign_issue",
					args: {
						issue: frm.doc.name,
						assignee: values.assignee,
						comment: values.comment,
					},
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
							frappe.show_alert({
								message: __("Issue reassigned successfully"),
								indicator: "green",
							});
						}
					},
				});
			},
			__("Reassign Issue"),
			__("Reassign")
		);
	},

	/**
	 * Record Steps Taken Action
	 */
	_addComment: function (frm) {
		frappe.prompt(
			[
				{
					fieldname: "comment",
					label: __("Steps Taken"),
					fieldtype: "Text",
					reqd: 1,
				},
				{
					fieldname: "due_at",
					label: __("Follow-up Date (Optional)"),
					fieldtype: "Datetime",
				},
			],
			function (values) {
				const comment = frm.add_child("grm_issue_comment");
				comment.user = frappe.session.user;
				comment.comment = values.comment;
				comment.due_at = values.due_at;

				frm.save();
				frappe.show_alert({
					message: __("Steps recorded successfully"),
					indicator: "green",
				});
			},
			__("Record Steps Taken"),
			__("Record")
		);
	},

	/**
	 * Load status information for button enablement
	 */
	_loadStatusInfo: function (frm) {
		// First, clear any existing buttons
		frm.clear_custom_buttons();

		if (frm.doc.status) {
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "GRM Issue Status",
					filters: { name: frm.doc.status },
					fieldname: [
						"initial_status",
						"open_status",
						"final_status",
						"rejected_status",
					],
				},
				callback: function (r) {
					if (r.message) {
						frm.doc.__onload = frm.doc.__onload || {};
						frm.doc.__onload.status_info = r.message;
						// Refresh buttons after loading status info
						frm.events._addActionButtons(frm);
					} else {
						// Still add basic buttons for submitted documents
						if (frm.doc.docstatus === 1) {
							frm.events._addActionButtons(frm);
						}
					}
				},
				error: function (err) {
					// Still add basic buttons for submitted documents
					if (frm.doc.docstatus === 1) {
						frm.events._addActionButtons(frm);
					}
				},
			});
		} else {
			// No status set, but still add basic buttons for submitted documents
			if (frm.doc.docstatus === 1) {
				frm.events._addActionButtons(frm);
			}
		}
	},

	refresh: function (frm) {
		// Handle location data
		if (frm.doc.issue_location) {
			try {
				const mapData = JSON.parse(frm.doc.issue_location)?.features[0];
				if (mapData && mapData.geometry.type.toLowerCase() === "point") {
					const [longitude, latitude] = mapData.geometry.coordinates;
					frm.doc.coordinates = `${latitude},${longitude}`;
				}
			} catch (error) {
				console.error("Error processing location data:", error);
			}
		}

		// Load status information and add action buttons (this now handles button loading)
		frm.events._loadStatusInfo(frm);

		// Add tracking URL button for draft issues
		if (frm.doc.docstatus === 0 && frm.doc.tracking_code) {
			frm.add_custom_button(__("Public Tracking URL"), function () {
				const tracking_url =
					window.location.origin + "/issue-tracker?code=" + frm.doc.tracking_code;
				frappe.prompt({
					fieldname: "url",
					label: __("Tracking URL"),
					fieldtype: "Small Text",
					read_only: 1,
					default: tracking_url,
				});
			});
		}

		// Show confidential information button
		if (frm.doc.citizen_type === "Confidential") {
			frm.add_custom_button(__("View Confidential Info"), function () {
				frappe.call({
					method: "get_citizen_name",
					doc: frm.doc,
					callback: function (r) {
						if (r.message) {
							const citizen = r.message;
							frappe.call({
								method: "get_contact_info",
								doc: frm.doc,
								callback: function (r2) {
									const contact = r2.message || "None";
									frappe.msgprint({
										title: __("Confidential Information"),
										indicator: "blue",
										message: __("Citizen: {0}<br>Contact: {1}", [
											citizen,
											contact,
										]),
									});
								},
							});
						}
					},
				});
			}).addClass("btn-primary");

			frm.set_intro(
				__(
					"This issue contains confidential citizen data that is securely stored using Frappe's Password field type."
				),
				"yellow"
			);
		}

		// Highlight escalated issues
		if (frm.doc.escalate_flag) {
			frm.get_field("escalate_flag").$input.css("background-color", "#ffccc7");
			frm.set_intro(__("This issue has been escalated and requires attention."), "red");
		}

		// Manual escalate button
		if (!frm.is_new() && !['Resolved', 'Closed'].includes(frm.doc.status)) {
			frm.add_custom_button(__('Escalate to Higher Level'), function() {
				let d = new frappe.ui.Dialog({
					title: __('Escalate Issue'),
					fields: [
						{
							fieldname: 'reason',
							label: __('Escalation Reason'),
							fieldtype: 'Small Text',
							reqd: 1
						}
					],
					primary_action_label: __('Escalate'),
					primary_action: function(values) {
						frappe.call({
							method: 'manual_escalate',
							doc: frm.doc,
							args: { reason: values.reason },
							callback: function(r) {
								if (r.message) {
									d.hide();
									frm.reload_doc();
								}
							}
						});
					}
				});
				d.show();
			}, __('Actions'));
		}

		// Resend notification button
		if (!frm.is_new()) {
			frm.add_custom_button(__('Resend Notification'), function() {
				let d = new frappe.ui.Dialog({
					title: __('Resend Notification'),
					fields: [
						{
							fieldname: 'notification_type',
							label: __('Notification Type'),
							fieldtype: 'Select',
							options: 'receipt\nacknowledgment\nin_progress\nresolved\nclosed\nescalated',
							reqd: 1
						}
					],
					primary_action_label: __('Send'),
					primary_action: function(values) {
						frappe.call({
							method: 'resend_notification',
							doc: frm.doc,
							args: { notification_type: values.notification_type },
							callback: function(r) {
								d.hide();
								frm.reload_doc();
							}
						});
					}
				});
				d.show();
			}, __('Actions'));
		}

		// Color-code SLA status
		if (frm.doc.sla_acknowledgment_status) {
			let color = {'On Time': 'green', 'Nearing Due': 'orange', 'Breached': 'red'}[frm.doc.sla_acknowledgment_status];
			if (color) frm.get_field('sla_acknowledgment_status').$wrapper.find('.like-disabled-input').css('color', color);
		}
		if (frm.doc.sla_resolution_status) {
			let color = {'On Time': 'green', 'Nearing Due': 'orange', 'Breached': 'red'}[frm.doc.sla_resolution_status];
			if (color) frm.get_field('sla_resolution_status').$wrapper.find('.like-disabled-input').css('color', color);
		}
	},

	setup: function (frm) {
		// Set up field filters
		frm.set_query("status", function () {
			return {
				query: "egrm.server_scripts.queries.get_status_by_project",
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		frm.set_query("category", function () {
			return {
				query: "egrm.server_scripts.queries.get_category_by_project",
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		frm.set_query("issue_type", function () {
			return {
				query: "egrm.server_scripts.queries.get_issue_type_by_project",
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		frm.set_query("administrative_region", function () {
			return {
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		frm.set_query("citizen_age_group", function () {
			return {
				query: "egrm.server_scripts.queries.get_age_group_by_project",
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		frm.set_query("citizen_group_1", function () {
			return {
				query: "egrm.server_scripts.queries.get_citizen_group_by_project",
				filters: {
					project: frm.doc.project || "",
					group_type: "1",
				},
			};
		});

		frm.set_query("citizen_group_2", function () {
			return {
				query: "egrm.server_scripts.queries.get_citizen_group_by_project",
				filters: {
					project: frm.doc.project || "",
					group_type: "2",
				},
			};
		});

		frm.set_query("assignee", function () {
			return {
				query: "egrm.server_scripts.queries.get_project_users",
				filters: {
					project: frm.doc.project || "",
				},
			};
		});

		// // Set default location to Kigali
		// if (!frm.doc.issue_location) {
		// 	const kigaliLocation = {
		// 		type: "FeatureCollection",
		// 		features: [
		// 			{
		// 				type: "Feature",
		// 				properties: {},
		// 				geometry: {
		// 					type: "Point",
		// 					coordinates: [30.0619, -1.9441],
		// 				},
		// 			},
		// 		],
		// 	};
		// 	frm.set_value("issue_location", JSON.stringify(kigaliLocation));
		// }
	},

	onload: function (frm) {
		// Set default status for new issues
		if (frm.is_new()) {
			if (frm.doc.project) {
				frappe.call({
					method: "egrm.server_scripts.queries.get_initial_status",
					args: {
						project: frm.doc.project,
					},
					callback: function (r) {
						if (r.message) {
							frm.set_value("status", r.message);
						}
					},
				});
			}

			// Set reporter to current user if empty
			if (!frm.doc.reporter) {
				frm.set_value("reporter", frappe.session.user);
			}
		}
	},

	project: function (frm) {
		// Clear dependent fields when project changes
		frm.set_value("status", "");
		frm.set_value("category", "");
		frm.set_value("issue_type", "");
		frm.set_value("administrative_region", "");
		frm.set_value("citizen_age_group", "");
		frm.set_value("citizen_group_1", "");
		frm.set_value("citizen_group_2", "");
		frm.set_value("assignee", "");

		// Set initial status for new project
		if (frm.doc.project) {
			frappe.call({
				method: "egrm.server_scripts.queries.get_initial_status",
				args: {
					project: frm.doc.project,
				},
				callback: function (r) {
					if (r.message) {
						frm.set_value("status", r.message);
					}
				},
			});
		}
	},

	category: function (frm) {
		// Auto-assign based on category department
		if (frm.doc.category && frm.doc.project) {
			frappe.call({
				method: "egrm.server_scripts.queries.get_department_for_category",
				args: {
					category: frm.doc.category,
				},
				callback: function (r) {
					if (r.message) {
						const department = r.message.department;
						const redirection = r.message.redirection;

						if (department) {
							if (redirection === "0") {
								// Assign to head
								frappe.call({
									method: "frappe.client.get_value",
									args: {
										doctype: "GRM Issue Department",
										filters: { name: department },
										fieldname: "head",
									},
									callback: function (r2) {
										if (r2.message && r2.message.head) {
											frm.set_value("assignee", r2.message.head);
										}
									},
								});
							} else if (redirection === "1") {
								// Assign to least loaded
								frappe.call({
									method: "egrm.server_scripts.queries.get_least_loaded_user",
									args: {
										department: department,
										project: frm.doc.project,
									},
									callback: function (r2) {
										if (r2.message) {
											frm.set_value("assignee", r2.message);
										}
									},
								});
							}
						}
					}
				},
			});
		}
	},

	citizen_type: function (frm) {
		// Clear non-confidential fields when switching to confidential
		if (frm.doc.citizen_type === "Confidential") {
			frm.set_value("citizen", "");
			frm.set_value("contact_information", "");
		}
		frm.refresh_fields();
	},

	contact_medium: function (frm) {
		frm.refresh_fields();

		// Require contact information for non-anonymous contacts
		if (frm.doc.contact_medium === "channel-alert") {
			if (frm.doc.citizen_type === "Confidential") {
				frm.toggle_reqd("contact_information", false);
			} else {
				frm.toggle_reqd("contact_information", true);
			}
		} else {
			frm.toggle_reqd("contact_information", false);
		}
	},

	issue_location: function (frm) {
		if (!frm.doc.issue_location) return;

		try {
			const mapData = JSON.parse(frm.doc.issue_location)?.features[0];
			if (!mapData) return;

			// Only allow Point geometry
			if (mapData.geometry.type.toLowerCase() !== "point") {
				frappe.msgprint({
					title: __("Invalid Location Type"),
					indicator: "red",
					message: __(
						"Only point locations are allowed. Please select a single point on the map."
					),
				});
				frm.set_value("issue_location", "");
				return;
			}

			// Extract coordinates
			const [longitude, latitude] = mapData.geometry.coordinates;
			frm.doc.coordinates = `${latitude},${longitude}`;
		} catch (error) {
			console.error("Error processing location data:", error);
			frappe.msgprint({
				title: __("Error"),
				indicator: "red",
				message: __("Invalid location data format"),
			});
		}
	},
});
