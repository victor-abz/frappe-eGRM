import { Model } from "@nozbe/watermelondb";
import { field, date, relation, children } from "@nozbe/watermelondb/decorators";

export default class GrmIssue extends Model {
	static table = "grm_issues";

	@relation("grm_projects", "project_id") project;
	@date("issue_date") issueDate;
	@date("intake_date") intakeDate;
	@relation("grm_issue_categories", "category_id") category;
	@relation("grm_issue_types", "issue_type_id") issueType;
	@relation("grm_issue_statuses", "status_id") status;
	@field("tracking_code") trackingCode;
	@field("description") description;
	@field("issue_location") issueLocation;
	@field("citizen_type") citizenType;
	@field("citizen") citizen;
	@field("citizen_confidential") citizenConfidential;
	@field("gender") gender;
	@field("contact_medium") contactMedium;
	@field("contact_info_type") contactInfoType;
	@field("contact_information") contactInformation;
	@field("contact_info_confidential") contactInfoConfidential;
	@relation("grm_issue_age_groups", "citizen_age_group_id") citizenAgeGroup;
	@relation("grm_issue_citizen_groups", "citizen_group_1_id") citizenGroup1;
	@relation("grm_issue_citizen_groups", "citizen_group_2_id") citizenGroup2;
	@relation("users", "reporter_id") reporter;
	@relation("users", "assignee_id") assignee;
	@relation("grm_administrative_regions", "administrative_region_id") administrativeRegion;
	@field("resolution_days") resolutionDays;
	@date("resolution_date") resolutionDate;
	@field("resolution_accepted") resolutionAccepted;
	@field("rating") rating;
	@field("escalate_flag") escalateFlag;
	@field("confirmed") confirmed;
	@relation("grm_issues", "amended_from_id") amendedFrom;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issue_attachments") attachments;
	@children("grm_issue_comments") comments;
	@children("grm_issue_escalation_reasons") escalationReasons;
	@children("grm_issue_logs") logs;
}
