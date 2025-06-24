import { Model } from "@nozbe/watermelondb";
import { field, date, relation, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssueCategory extends Model {
	static table = "grm_issue_categories";

	@field("category_name") categoryName;
	@field("label") label;
	@field("abbreviation") abbreviation;
	@relation("grm_issue_departments", "assigned_department_id") assignedDepartment;
	@relation("grm_issue_departments", "assigned_appeal_department_id") assignedAppealDepartment;
	@relation("grm_issue_departments", "assigned_escalation_department_id")
	assignedEscalationDepartment;
	@field("confidentiality_level") confidentialityLevel;
	@field("redirection_protocol") redirectionProtocol;
	@relation("grm_administrative_level_types", "administrative_level_id") administrativeLevel;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
}
