import { Model } from "@nozbe/watermelondb";
import { field, date, relation, children } from "@nozbe/watermelondb/decorators";

export default class GrmAdministrativeRegion extends Model {
	static table = "grm_administrative_regions";
	static associations = {
		grm_administrative_regions: { type: "belongs_to", key: "parent_region_id" },
	};

	@field("region_name") regionName;
	@relation("grm_administrative_level_types", "administrative_level_id") administrativeLevel;
	@relation("grm_administrative_regions", "parent_region_id") parentRegion;
	@field("location") location;
	@relation("grm_projects", "project_id") project;
	@field("path") path;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_administrative_regions") children;
}
