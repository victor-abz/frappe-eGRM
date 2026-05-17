frappe.listview_settings["GRM Issue"] = {
	add_fields: ["status", "docstatus", "project"],

	has_indicator_for_draft: 1,
	has_indicator_for_cancelled: 1,

	_status_map: null,
	_status_loading: false,

	onload: function (listview) {
		this._ensure_status_map(listview);
	},

	refresh: function (listview) {
		this._ensure_status_map(listview);
	},

	_ensure_status_map: function (listview) {
		const settings = frappe.listview_settings["GRM Issue"];
		if (settings._status_map || settings._status_loading) return;
		settings._status_loading = true;
		frappe.db
			.get_list("GRM Issue Status", {
				fields: [
					"name",
					"status_name",
					"final_status",
					"rejected_status",
					"open_status",
					"initial_status",
				],
				limit: 500,
			})
			.then((rows) => {
				const map = {};
				(rows || []).forEach((r) => {
					map[r.name] = {
						label: r.status_name || r.name,
						color: _grm_color_for(r),
					};
				});
				settings._status_map = map;
				try {
					if (listview && listview.doctype === "GRM Issue") {
						listview.render_list();
					}
				} catch (e) {
					// list view may be torn down; ignore
				}
			})
			.always(() => {
				settings._status_loading = false;
			});
	},

	get_indicator: function (doc) {
		const settings = frappe.listview_settings["GRM Issue"];
		const map = settings._status_map || {};
		const entry = doc.status ? map[doc.status] : null;
		if (entry) {
			return [__(entry.label), entry.color, "status,=," + doc.status];
		}
		if (doc.docstatus === 2) {
			return [__("Cancelled"), "red", "docstatus,=,2"];
		}
		// Either no status set yet, or the status map is still loading.
		return [__("Pending"), "grey", "status,is,not set"];
	},
};

function _grm_color_for(row) {
	// Order matters: a status can carry multiple flags (e.g. "New" is both
	// initial_status=1 and open_status=1; "Resolved" is final_status=1 and
	// sometimes open_status=1). The visual priority we want is:
	//   rejected  -> red       (Rejected)
	//   final     -> green     (Resolved, Closed)
	//   initial   -> blue      (New)
	//   open      -> orange    (In Progress and other working states)
	if (row.rejected_status) return "red";
	if (row.final_status) return "green";
	if (row.initial_status) return "blue";
	if (row.open_status) return "orange";
	return "grey";
}
