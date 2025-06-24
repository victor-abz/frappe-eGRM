import { Model } from "@nozbe/watermelondb";
import { field, date, relation, children } from "@nozbe/watermelondb/decorators";

export default class GrmAdministrativeLevelType extends Model {
	static table = "grm_administrative_level_types";

	@field("level_name") levelName;
	@field("level_order") levelOrder;
	@relation("grm_projects", "project_id") project;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_administrative_regions") administrativeRegions;
	@children("grm_issue_categories") issueCategories;
}
