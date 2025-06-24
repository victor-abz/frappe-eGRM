import { Model } from "@nozbe/watermelondb";
import { field, date, relation } from "@nozbe/watermelondb/decorators";

export default class GrmIssueAttachment extends Model {
	static table = "grm_issue_attachments";
	static associations = {
		grm_issues: { type: "belongs_to", key: "grm_issue_id" },
	};

	@relation("grm_issues", "grm_issue_id") issue;
	@field("attachment") attachment;
	@field("file_name") fileName;
	@field("local_url") localUrl;
	@field("uploaded") uploaded;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;
}
