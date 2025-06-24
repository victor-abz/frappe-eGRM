import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class User extends Model {
	static table = "users";

	@field("full_name") fullName;
	@field("email") email;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") reportedIssues;
	@children("grm_issue_comments") comments;
	@children("grm_issue_escalation_reasons") escalationReasons;
	@children("grm_issue_logs") logs;
	@children("grm_issue_departments") departmentHeads;
}
