import { Model } from "@nozbe/watermelondb";
import { field, date, children } from "@nozbe/watermelondb/decorators";

export default class GrmProject extends Model {
	static table = "grm_projects";

	@field("title") title;
	@field("project_code") projectCode;
	@field("description") description;
	@date("start_date") startDate;
	@date("end_date") endDate;
	@field("is_active") isActive;
	@field("logo") logo;
	@field("default_language") defaultLanguage;
	@field("auto_escalation_days") autoEscalationDays;
	@field("enable_citizen_feedback") enableCitizenFeedback;
	@date("created_at") createdAt;
	@date("updated_at") updatedAt;

	@children("grm_issues") issues;
	@children("grm_project_links") projectLinks;
	@children("grm_administrative_regions") administrativeRegions;
	@children("grm_administrative_level_types") administrativeLevelTypes;
}
