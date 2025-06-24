import { Model } from "@nozbe/watermelondb";
import { field, date, relation } from "@nozbe/watermelondb/decorators";

export default class GrmIssueEscalationReason extends Model {
	static table = "grm_issue_escalation_reasons";
	static associations = {
		grm_issues: { type: "belongs_to", key: "grm_issue_id" },
	};

	@relation("grm_issues", "grm_issue_id") issue;
	@relation("users", "user_id") user;
	@field("comment") comment;
	@date("due_at") dueAt;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;
}
