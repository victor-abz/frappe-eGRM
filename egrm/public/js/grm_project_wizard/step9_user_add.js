// ---------------------------------------------------------------------------
// Step 9 (Phase D) — Single-add form
//
// `GRMWizardStep9UserAdd` is the "Single user" face of the Add panel below
// the users list. It's *doctype-driven*: required vs optional pills come
// from the same `get_assignment_field_meta` payload the bulk-import mapper
// uses (plan §Engineering Conventions clause 2). The region picker is a
// cascade — one Link control per project level (highest first), each
// filtered to its parent's children. When the operator picks a Project
// Role with `admin_level` set, the cascade levels below that admin_level
// are read-only and cleared (plan §D.2).
// ---------------------------------------------------------------------------

class GRMWizardStep9UserAdd {
	constructor(opts) {
		this.project = opts.project; // GRM Project doc-ish ({name, ...})
		this.$mount = opts.$mount; // jQuery wrapper for the slot
		this.on_added = opts.on_added || (() => {}); // callback when a row is created
		this.field_meta = null; // populated on first render()
		this.controls = {}; // user / role / department / position_title
		this.region_cascade_controls = []; // one Link control per level (high→low)
	}

	async render() {
		// Skeleton first so spinners are visible while we fetch meta.
		this.$mount.html(`
            <div class="grm-step9-add-form">
              <h5>${__("Add a single user")}</h5>
              <div class="grm-step9-add-loading text-muted">${__("Loading…")}</div>
            </div>
        `);

		if (!this.field_meta) {
			try {
				const r = await frappe.call({
					method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.get_assignment_field_meta",
					args: { project: this.project.name },
				});
				this.field_meta = r.message || {};
			} catch (e) {
				this.$mount
					.find(".grm-step9-add-loading")
					.replaceWith(
						`<div class="alert alert-danger">${__(
							"Could not load form metadata."
						)}</div>`
					);
				return;
			}
		}

		// Replace skeleton with the real form layout. The slots match the
		// controls we mount below in `build_controls`.
		this.$mount.find(".grm-step9-add-form").html(`
            <h5>${__("Add a single user")}</h5>
            <div class="row">
              <div class="col-md-6"><div class="form-group" data-field="user"></div></div>
              <div class="col-md-6"><div class="form-group" data-field="role"></div></div>
            </div>
            <div class="row">
              <div class="col-md-6"><div class="form-group" data-field="administrative_region"></div></div>
              <div class="col-md-6"><div class="form-group" data-field="department"></div></div>
            </div>
            <div class="row">
              <div class="col-md-12"><div class="form-group" data-field="position_title"></div></div>
            </div>
            <div class="grm-step9-add-actions">
              <button type="button" class="btn btn-primary grm-step9-add-submit">${__(
					"Add user"
				)}</button>
              <button type="button" class="btn btn-default grm-step9-add-clear">${__(
					"Clear"
				)}</button>
            </div>
        `);

		this.controls = {};
		this.region_cascade_controls = [];
		this.build_controls();
		this.wire_actions();
	}

	/** Look up `fieldname` in `assignment_fields[]` and report `reqd`. */
	_is_assignment_required(fieldname) {
		const f = (this.field_meta.assignment_fields || []).find((x) => x.fieldname === fieldname);
		return !!(f && f.reqd);
	}

	/** Inject a red asterisk after the label text iff the field is required. */
	_label_with_reqd(label, required) {
		return required ? `${label} <span class="text-danger">*</span>` : label;
	}

	build_controls() {
		// user — Link to User. The doctype marks `user` as reqd, but we
		// read from the meta payload to avoid hard-coding the flag.
		const user_required = this._is_assignment_required("user");
		this.controls.user = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "User",
				label: this._label_with_reqd(__("User"), user_required),
				reqd: user_required ? 1 : 0,
				placeholder: __("Search by email or name"),
			},
			parent: this.$mount.find('[data-field="user"]')[0],
			render_input: true,
		});

		// role — Link to GRM Project Role, filtered to the active roles
		// for THIS project. Picking a role triggers the region cascade
		// reset below (`on_role_change`).
		const role_required = this._is_assignment_required("role");
		this.controls.role = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "GRM Project Role",
				label: this._label_with_reqd(__("Role"), role_required),
				reqd: role_required ? 1 : 0,
				get_query: () => ({
					filters: { project: this.project.name, is_active: 1 },
				}),
				onchange: () => this.on_role_change(),
			},
			parent: this.$mount.find('[data-field="role"]')[0],
			render_input: true,
		});

		// administrative_region — D.2 cascading picker (one Link per level).
		this.build_region_cascade();

		// department — Link to GRM Issue Department scoped to this project.
		// The doctype validator additionally checks the project link table,
		// but the simple `project` filter is good enough for the picker.
		this.controls.department = frappe.ui.form.make_control({
			df: {
				fieldtype: "Link",
				options: "GRM Issue Department",
				label: __("Department"),
				get_query: () => ({ filters: { project: this.project.name } }),
			},
			parent: this.$mount.find('[data-field="department"]')[0],
			render_input: true,
		});

		// position_title — free-text Data field.
		this.controls.position_title = frappe.ui.form.make_control({
			df: { fieldtype: "Data", label: __("Position") },
			parent: this.$mount.find('[data-field="position_title"]')[0],
			render_input: true,
		});
	}

	build_region_cascade() {
		const $parent = this.$mount.find('[data-field="administrative_region"]');
		const region_required = this._is_assignment_required("administrative_region");
		$parent.html(`
            <label>${this._label_with_reqd(__("Region"), region_required)}</label>
            <div class="grm-region-cascade"></div>
        `);

		const $cascade = $parent.find(".grm-region-cascade");
		this.region_cascade_controls = [];

		// Levels arrive ordered by `level_order ASC` from the server, i.e.
		// highest level (smallest number, e.g. Province=1) first. We mount
		// one Link control per level; each filters to children of the
		// level above.
		const levels = this.field_meta.project_levels || [];
		levels.forEach((level, idx) => {
			const $slot = $('<div class="grm-region-cascade-slot"></div>').appendTo($cascade);
			const ctrl = frappe.ui.form.make_control({
				df: {
					fieldtype: "Link",
					options: "GRM Administrative Region",
					label: level.level_name || level.name,
					placeholder: __("Pick {0}", [level.level_name || level.name]),
					get_query: () => {
						const filters = {
							project: this.project.name,
							administrative_level: level.name,
						};
						if (idx > 0) {
							const parent_value =
								this.region_cascade_controls[idx - 1] &&
								this.region_cascade_controls[idx - 1].get_value();
							if (parent_value) {
								filters.parent_region = parent_value;
							} else {
								// No parent picked yet — return nothing so
								// the dropdown reads "no matches" rather
								// than offering every region in the project.
								return { filters: { name: ["=", "__none__"] } };
							}
						}
						return { filters };
					},
					onchange: () => {
						// Picking a value at level `idx` invalidates any
						// selection at deeper levels — clear them so the
						// submit value reflects the deepest *consistent*
						// ancestry.
						for (let j = idx + 1; j < this.region_cascade_controls.length; j++) {
							const lower = this.region_cascade_controls[j];
							if (lower && lower.set_value) lower.set_value("");
						}
					},
				},
				parent: $slot[0],
				render_input: true,
			});
			this.region_cascade_controls.push(ctrl);
		});
	}

	/**
	 * Walk the cascade from the deepest level back to the highest and
	 * return the first non-empty value — that's the most-specific region
	 * the operator has picked.
	 */
	get_selected_region() {
		for (let i = this.region_cascade_controls.length - 1; i >= 0; i--) {
			const v =
				this.region_cascade_controls[i] && this.region_cascade_controls[i].get_value();
			if (v) return v;
		}
		return null;
	}

	on_role_change() {
		const role_id = this.controls.role && this.controls.role.get_value();
		if (!role_id) {
			// No role picked → no cascade restriction.
			this.set_cascade_min_level(null);
			return;
		}
		// Avoid a get_value() round-trip: the role meta we already loaded
		// includes `admin_level` for every active project role.
		const meta = (this.field_meta.project_roles || []).find((r) => r.name === role_id);
		if (meta) {
			this.set_cascade_min_level(meta.admin_level || null);
			return;
		}
		// Fall back to the DB if the role isn't in the cached meta (rare —
		// happens only if a role was added between page load and click).
		frappe.db.get_value("GRM Project Role", role_id, "admin_level").then((r) => {
			const role_admin_level = (r && r.message && r.message.admin_level) || null;
			this.set_cascade_min_level(role_admin_level);
		});
	}

	/**
	 * Disable cascade slots strictly *below* the role's `admin_level`.
	 * The role's `admin_level` is the lowest level the role can be
	 * assigned at, so picking deeper would violate the server's
	 * `create_assignment` invariant — block it in the UI to match.
	 */
	set_cascade_min_level(role_admin_level) {
		const levels = this.field_meta.project_levels || [];
		if (!role_admin_level) {
			// No restriction — every slot is editable.
			this.region_cascade_controls.forEach((ctrl) => {
				if (ctrl && ctrl.df) ctrl.df.read_only = 0;
				if (ctrl && ctrl.refresh) ctrl.refresh();
			});
			return;
		}
		const role_level_idx = levels.findIndex((l) => l.name === role_admin_level);
		if (role_level_idx === -1) return;

		this.region_cascade_controls.forEach((ctrl, idx) => {
			if (!ctrl || !ctrl.df) return;
			const should_disable = idx > role_level_idx;
			ctrl.df.read_only = should_disable ? 1 : 0;
			if (should_disable && ctrl.set_value) ctrl.set_value("");
			if (ctrl.refresh) ctrl.refresh();
		});
	}

	wire_actions() {
		this.$mount.find(".grm-step9-add-submit").on("click", () => this.submit());
		this.$mount.find(".grm-step9-add-clear").on("click", () => this.clear_form());
	}

	async submit() {
		// Review fix B9: double-submit guard. Without this a rapid
		// double-click on the "Add" button can fire two concurrent
		// create_assignment RPCs — second one races on duplicate-user
		// detection and the operator gets a confusing error toast.
		if (this._submitting) return;
		const user = this.controls.user && this.controls.user.get_value();
		const role = this.controls.role && this.controls.role.get_value();
		if (!user || !role) {
			frappe.msgprint({
				title: __("Required fields missing"),
				message: __("User and Role are required."),
				indicator: "red",
			});
			return;
		}
		const region = this.get_selected_region();
		const department = this.controls.department && this.controls.department.get_value();
		const position_title =
			this.controls.position_title && this.controls.position_title.get_value();

		this._submitting = true;
		frappe.dom.freeze(__("Adding user…"));
		try {
			const r = await frappe.call({
				method: "egrm.egrm.page.grm_project_wizard.grm_project_wizard.create_assignment",
				args: {
					project: this.project.name,
					user,
					role,
					administrative_region: region,
					department: department || null,
					position_title: position_title || null,
				},
			});
			frappe.show_alert({ message: __("User added."), indicator: "green" });
			this.clear_form();
			this.on_added(r.message);
		} catch (e) {
			// frappe.call already surfaces the error toast; nothing to do.
		} finally {
			frappe.dom.unfreeze();
			this._submitting = false;
		}
	}

	clear_form() {
		// `set_value("")` on a Link clears it; on Data writes empty.
		Object.values(this.controls).forEach((c) => {
			if (c && c.set_value) c.set_value("");
		});
		(this.region_cascade_controls || []).forEach((c) => {
			if (c && c.set_value) c.set_value("");
		});
	}
}

// ---------------------------------------------------------------------------
