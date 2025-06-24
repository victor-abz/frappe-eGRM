

## Issue Management API (`issue.py`)

These endpoints are for direct, real-time interaction with individual issues when the app is online.

- `GET /api/method/egrm.api.issue.list`: List issues with filters for project, status, assignee, etc.
- `GET /api/method/egrm.api.issue.get`: Get full details for a single issue.
- `POST /api/method/egrm.api.issue.create`: Create a new issue.
- `PUT /api/method/egrm.api.issue.update`: Update an existing issue.
- `POST /api/method/egrm.api.issue.assign`: Assign an issue to a user.
- `POST /api/method/egrm.api.issue.resolve`: Mark an issue as resolved.
- `POST /api/method/egrm.api.issue.reopen`: Reopen a resolved issue.
- `POST /api/method/egrm.api.issue.escalate`: Escalate an issue.

---

## Lookup API (`lookup.py`)

These endpoints provide data for populating UI elements like dropdowns and selection lists. Each endpoint returns a list of the corresponding items. The `project_id` parameter can be used to filter the results.

- `GET /api/method/egrm.api.lookup.categories`
- `GET /api/method/egrm.api.lookup.types`
- `GET /api/method/egrm.api.lookup.statuses`
- `GET /api/method/egrm.api.lookup.age_groups`
- `GET /api/method/egrm.api.lookup.citizen_groups`
- `GET /api/method/egrm.api.lookup.departments`
- `GET /api/method/egrm.api.lookup.regions`
- `GET /api/method/egrm.api.lookup.projects`

---

## Attachment API (`attachment.py`)

These endpoints are for handling file attachments when the app is online.

- `POST /api/method/egrm.api.attachment.upload`: Upload a file and attach it to an issue. Requires `issue_id` and file data.
- `GET /api/method/egrm.api.attachment.list`: List all attachments for a given `issue_id`.
- `GET /api/method/egrm.api.attachment.download`: Get a download URL for a specific `attachment_id`.
