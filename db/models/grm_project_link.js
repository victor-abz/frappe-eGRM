import { Model } from "@nozbe/watermelondb";
import { field, date, relation } from "@nozbe/watermelondb/decorators";

export default class GrmProjectLink extends Model {
	static table = "grm_project_links";

	@relation("grm_projects", "project_id") project;
	@field("parent_id") parentId;
	@field("parent_type") parentType;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;
}
