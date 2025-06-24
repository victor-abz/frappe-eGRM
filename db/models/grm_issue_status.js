import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueStatus extends Model {
	static table = "grm_issue_statuses";

	@field("status_name") statusName;
	@field("final_status") finalStatus;
	@field("initial_status") initialStatus;
	@field("rejected_status") rejectedStatus;
	@field("open_status") openStatus;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
}
