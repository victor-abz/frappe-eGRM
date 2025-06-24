import { appSchema, tableSchema } from '@nozbe/watermelondb'

export default appSchema({
  version: 1,
  tables: [
    tableSchema({
      name: 'grm_issues',
      columns: [
        { name: 'project_id', type: 'string', isIndexed: true },
        { name: 'issue_date', type: 'number' },
        { name: 'intake_date', type: 'number' },
        { name: 'category_id', type: 'string', isIndexed: true },
        { name: 'issue_type_id', type: 'string', isIndexed: true },
        { name: 'status_id', type: 'string', isIndexed: true },
        { name: 'tracking_code', type: 'string', isOptional: true },
        { name: 'description', type: 'string' },
        { name: 'issue_location', type: 'string', isOptional: true },
        { name: 'citizen_type', type: 'string' },
        { name: 'citizen', type: 'string', isOptional: true },
        { name: 'citizen_confidential', type: 'string', isOptional: true },
        { name: 'gender', type: 'string', isOptional: true },
        { name: 'contact_medium', type: 'string' },
        { name: 'contact_info_type', type: 'string', isOptional: true },
        { name: 'contact_information', type: 'string', isOptional: true },
        { name: 'contact_info_confidential', type: 'string', isOptional: true },
        { name: 'citizen_age_group_id', type: 'string', isOptional: true, isIndexed: true },
        { name: 'citizen_group_1_id', type: 'string', isOptional: true, isIndexed: true },
        { name: 'citizen_group_2_id', type: 'string', isOptional: true, isIndexed: true },
        { name: 'reporter_id', type: 'string', isIndexed: true },
        { name: 'assignee_id', type: 'string', isOptional: true, isIndexed: true },
        { name: 'administrative_region_id', type: 'string', isIndexed: true },
        { name: 'resolution_days', type: 'number', isOptional: true },
        { name: 'resolution_date', type: 'number', isOptional: true },
        { name: 'resolution_accepted', type: 'string', isOptional: true },
        { name: 'rating', type: 'number', isOptional: true },
        { name: 'escalate_flag', type: 'boolean', isOptional: true },
        { name: 'confirmed', type: 'boolean', isOptional: true },
        { name: 'amended_from_id', type: 'string', isOptional: true, isIndexed: true },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ]
    }),
    tableSchema({
      name: 'grm_projects',
      columns: [
        { name: 'title', type: 'string' },
        { name: 'project_code', type: 'string', isIndexed: true },
        { name: 'description', type: 'string', isOptional: true },
        { name: 'start_date', type: 'number', isOptional: true },
        { name: 'end_date', type: 'number', isOptional: true },
        { name: 'is_active', type: 'boolean' },
        { name: 'logo', type: 'string', isOptional: true },
        { name: 'default_language', type: 'string', isOptional: true },
        { name: 'auto_escalation_days', type: 'number', isOptional: true },
        { name: 'enable_citizen_feedback', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ]
    }),
    tableSchema({
        name: 'grm_issue_age_groups',
        columns: [
            { name: 'age_group', type: 'string' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_attachments',
        columns: [
            { name: 'grm_issue_id', type: 'string', isIndexed: true },
            { name: 'attachment', type: 'string' },
            { name: 'file_name', type: 'string', isOptional: true },
            { name: 'local_url', type: 'string', isOptional: true },
            { name: 'uploaded', type: 'boolean' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_categories',
        columns: [
            { name: 'category_name', type: 'string' },
            { name: 'label', type: 'string' },
            { name: 'abbreviation', type: 'string' },
            { name: 'assigned_department_id', type: 'string', isIndexed: true },
            { name: 'assigned_appeal_department_id', type: 'string', isOptional: true, isIndexed: true },
            { name: 'assigned_escalation_department_id', type: 'string', isOptional: true, isIndexed: true },
            { name: 'confidentiality_level', type: 'string' },
            { name: 'redirection_protocol', type: 'string' },
            { name: 'administrative_level_id', type: 'string', isOptional: true, isIndexed: true },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_citizen_groups',
        columns: [
            { name: 'group_name', type: 'string' },
            { name: 'group_type', type: 'string' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_departments',
        columns: [
            { name: 'department_name', type: 'string' },
            { name: 'head_id', type: 'string', isOptional: true, isIndexed: true },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_types',
        columns: [
            { name: 'type_name', type: 'string' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_statuses',
        columns: [
            { name: 'status_name', type: 'string' },
            { name: 'final_status', type: 'boolean' },
            { name: 'initial_status', type: 'boolean' },
            { name: 'rejected_status', type: 'boolean' },
            { name: 'open_status', type: 'boolean' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_administrative_regions',
        columns: [
            { name: 'region_name', type: 'string' },
            { name: 'administrative_level_id', type: 'string', isIndexed: true },
            { name: 'parent_region_id', type: 'string', isOptional: true, isIndexed: true },
            { name: 'location', type: 'string', isOptional: true },
            { name: 'project_id', type: 'string', isIndexed: true },
            { name: 'path', type: 'string', isOptional: true },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_comments',
        columns: [
            { name: 'grm_issue_id', type: 'string', isIndexed: true },
            { name: 'user_id', type: 'string', isIndexed: true },
            { name: 'comment', type: 'string' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_escalation_reasons',
        columns: [
            { name: 'grm_issue_id', type: 'string', isIndexed: true },
            { name: 'user_id', type: 'string', isIndexed: true },
            { name: 'comment', type: 'string' },
            { name: 'due_at', type: 'number' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_issue_logs',
        columns: [
            { name: 'grm_issue_id', type: 'string', isIndexed: true },
            { name: 'text', type: 'string' },
            { name: 'user_id', type: 'string', isIndexed: true },
            { name: 'timestamp', type: 'number' },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_project_links',
        columns: [
            { name: 'project_id', type: 'string', isIndexed: true },
            { name: 'parent_id', type: 'string', isIndexed: true },
            { name: 'parent_type', type: 'string', isIndexed: true },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
        name: 'grm_administrative_level_types',
        columns: [
            { name: 'level_name', type: 'string' },
            { name: 'level_order', type: 'number' },
            { name: 'project_id', type: 'string', isIndexed: true },
            { name: 'created_at', type: 'number' },
            { name: 'updated_at', type: 'number' },
        ]
    }),
    tableSchema({
      name: 'users',
      columns: [
        { name: 'full_name', type: 'string', isOptional: true },
        { name: 'email', type: 'string' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ]
    }),
  ]
})
