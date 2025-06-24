import { Model } from "@nozbe/watermelondb";
import { field, date, relation } from "@nozbe/watermelondb/decorators";

export default class GrmIssueLog extends Model {
	static table = "grm_issue_logs";
	static associations = {
		grm_issues: { type: "belongs_to", key: "grm_issue_id" },
	};

	@relation("grm_issues", "grm_issue_id") issue;
	@field("text") text;
	@relation("users", "user_id") user;
	@date("timestamp") timestamp;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;
}
