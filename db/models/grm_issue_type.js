import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueType extends Model {
	static table = "grm_issue_types";

	@field("type_name") typeName;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
}
