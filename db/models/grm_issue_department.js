import { Model } from "@nozbe/watermelondb";
import { field, date, relation, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueDepartment extends Model {
	static table = "grm_issue_departments";

	@field("department_name") departmentName;
	@relation("users", "head_id") head;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issue_categories") issueCategories;
	@children("grm_project_links") projectLinks;
}
