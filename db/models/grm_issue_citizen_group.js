import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueCitizenGroup extends Model {
	static table = "grm_issue_citizen_groups";

	@field("group_name") groupName;
	@field("group_type") groupType;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
}
