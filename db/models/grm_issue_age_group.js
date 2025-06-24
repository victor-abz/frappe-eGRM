import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueAgeGroup extends Model {
	static table = "grm_issue_age_groups";

	@field("age_group") ageGroup;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
}
