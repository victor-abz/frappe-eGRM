/**
 * Point the desk map at Rwanda instead of Mumbai.
 *
 * Frappe hardcodes `frappe.utils.map_defaults.center = [19.08, 72.8961]`
 * (Mumbai, zoom 13) in `frappe/public/js/frappe/utils/utils.js`. Every
 * Geolocation control — including "Issue Location" on GRM Issue — calls
 * `map.setView(frappe.utils.map_defaults.center, ...)` when it initialises,
 * so an issue with no coordinates yet opens on the wrong continent.
 *
 * The framework reads those values at map-init time rather than capturing
 * them at load, so overriding the object here is enough; there is no need to
 * patch the control itself. We mutate in place rather than reassigning so any
 * other key on `map_defaults` (tile URLs, attribution) is left alone.
 *
 * Centre is Rwanda's approximate centroid at a whole-country zoom, so an
 * officer can see every district and pan to the one they need, instead of
 * being dropped into one street in Kigali.
 *
 * Idempotent: safe if the bundle is included more than once.
 */
(function () {
	if (typeof frappe === "undefined" || !frappe.utils || !frappe.utils.map_defaults) return;
	if (frappe.utils.map_defaults.__egrm_centred_on_rwanda) return;

	frappe.utils.map_defaults.center = [-1.9403, 29.8739];
	frappe.utils.map_defaults.zoom = 8;
	frappe.utils.map_defaults.__egrm_centred_on_rwanda = true;
})();
