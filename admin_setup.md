# EGRM - Complete Setup and User Guide

## Table of Contents
- [Administrator Setup Guide](#administrator-setup-guide)
- [Project Manager Guide](#project-manager-guide)
- [Department Head Guide](#department-head-guide)
- [Field Officer Guide](#field-officer-guide)
- [User Management](#user-management)
- [Troubleshooting](#troubleshooting)

---

## Administrator Setup Guide

### Initial System Setup Checklist

#### Step 1: Create Administrative Hierarchy
Before creating any projects, establish the administrative structure:

1. **Navigate to GRM Administrative Level Type**
   - Go to: **Home → EGRM → GRM Administrative Level Type → New**
   - Create hierarchy levels in order (lowest to highest):
     ```
     Level Name: Country    | Level Order: 1
     Level Name: Province   | Level Order: 2
     Level Name: District   | Level Order: 3
     Level Name: Sector     | Level Order: 4
     Level Name: Cell       | Level Order: 5
     ```
   - Save each level

2. **Create Your First Project**
   - Go to: **Home → EGRM → GRM Project → New**
   - Fill required fields:
     ```
     Project Title: "Rwanda National GRM"
     Project Code: "RW-NGRM-2025" (must be unique)
     Description: "National Grievance and Redress Mechanism"
     Start Date: [Today's date]
     Is Active: ✅ (checked)
     Auto Escalation Days: 30
     Enable Citizen Feedback: ✅ (checked)
     ```
   - **Save** the project

#### Step 2: Setup Administrative Regions
Create your geographical hierarchy starting from the top:

1. **Create Country Level**
   - Go to: **GRM Administrative Region → New**
   ```
   Region Name: Rwanda
   Administrative Level: Country
   Parent Region: [Leave empty - this is top level]
   Project: RW-NGRM-2025
   Location: [Optional - add GPS coordinates]
   ```

2. **Create Provinces**
   - Create each province as a child of Rwanda:
   ```
   Region Name: Kigali Province
   Administrative Level: Province
   Parent Region: Rwanda
   Project: RW-NGRM-2025
   ```
   - Repeat for: Eastern Province, Northern Province, Southern Province, Western Province

3. **Create Districts**
   - Create districts under each province:
   ```
   Region Name: Nyarugenge District
   Administrative Level: District
   Parent Region: Kigali Province
   Project: RW-NGRM-2025
   ```

4. **Continue hierarchy** down to Sectors and Cells as needed

#### Step 3: Configure Issue Classifications

1. **Create Issue Departments**
   - Go to: **GRM Issue Department → New**
   - Create departments that will handle issues:
   ```
   Department Name: Infrastructure & Public Works
   Head: [Select a user who will lead this department]
   Project Link: Add row → Project: RW-NGRM-2025
   ```
   - Common departments to create:
     - Infrastructure & Public Works
     - Health Services
     - Education Services
     - Social Services
     - Environmental Protection
     - Security & Safety

2. **Create Issue Statuses**
   - Go to: **GRM Issue Status → New**
   - Create these essential statuses:

   **Initial Status (for new issues):**
   ```
   Status Name: Open
   Initial Status: ✅ (checked)
   Open Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Active Work Statuses:**
   ```
   Status Name: Assigned
   Open Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   ```
   Status Name: In Progress
   Open Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Resolution Status:**
   ```
   Status Name: Resolved
   Final Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Closure Status:**
   ```
   Status Name: Closed
   Final Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Rejection Status:**
   ```
   Status Name: Rejected
   Rejected Status: ✅ (checked)
   Final Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

3. **Create Issue Categories**
   - Go to: **GRM Issue Category → New**
   - Create categories that match your departments:

   ```
   Category Name: Infrastructure Issues
   Display Label: Infrastructure & Public Works
   Abbreviation: INFRA
   Assigned Department: Infrastructure & Public Works
   Confidentiality Level: Public
   Redirection Protocol: 0=Assign to head
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Common categories to create:**
   - Water Supply Issues (WATER) → Infrastructure & Public Works
   - Road Maintenance (ROADS) → Infrastructure & Public Works
   - Healthcare Access (HEALTH) → Health Services
   - Education Quality (EDU) → Education Services
   - Social Welfare (SOCIAL) → Social Services
   - Environmental Concerns (ENV) → Environmental Protection

4. **Create Issue Types**
   - Go to: **GRM Issue Type → New**
   - Create general types that apply across categories:
   ```
   Type Name: Complaint
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Common types to create:**
   - Complaint
   - Request for Service
   - Suggestion
   - Information Request
   - Appeal

#### Step 4: Setup Citizen Classifications

1. **Create Age Groups**
   - Go to: **GRM Issue Age Group → New**
   ```
   Age Group Name: Child (0-17)
   Min Age: 0
   Max Age: 17
   ```

   **Create these age groups:**
   - Child (0-17)
   - Young Adult (18-30)
   - Adult (31-60)
   - Senior (60+)

2. **Create Citizen Groups**
   - Go to: **GRM Issue Citizen Group → New**

   **Group Type 1 (Primary Demographics):**
   ```
   Group Name: Women
   Group Type: 1
   ```
   - Women
   - Men
   - Youth
   - Elderly
   - Disabled

   **Group Type 2 (Occupation/Social Groups):**
   ```
   Group Name: Farmers
   Group Type: 2
   ```
   - Farmers
   - Traders
   - Students
   - Civil Servants
   - Unemployed

#### Step 5: Create User Accounts and Assignments

1. **Create User Accounts**
   - Go to: **Users → New User**
   - For each team member:
   ```
   Email: john.doe@ministry.gov.rw
   First Name: John
   Last Name: Doe
   Full Name: John Doe
   Send Welcome Email: ✅ (checked)
   ```

2. **Assign Roles to Users**
   - Edit each user and in the **Roles** section, add appropriate roles:
   - **GRM Administrator**: Full system access
   - **GRM Project Manager**: Project management
   - **GRM Department Head**: Department oversight
   - **GRM Field Officer**: Issue handling
   - **GRM Analyst**: Reporting only

3. **Create Project Assignments**
   - Go to: **GRM User Project Assignment → New**

   **For Department Head:**
   ```
   User: john.doe@ministry.gov.rw
   Project: RW-NGRM-2025
   Role: GRM Department Head
   Department: Infrastructure & Public Works
   Administrative Region: [Select appropriate region]
   Is Active: ✅ (checked)
   Position Title: Director of Public Works
   ```

   **For Field Officer:**
   ```
   User: field.officer@ministry.gov.rw
   Project: RW-NGRM-2025
   Role: GRM Field Officer
   Administrative Region: Nyarugenge District
   Is Active: ✅ (checked)
   Position Title: Field Officer
   ```

#### Step 6: Send Activation Codes
1. **For Government Workers (Department Heads and Field Officers):**
   - After creating assignments, the system generates activation codes
   - Go to the **GRM User Project Assignment** record
   - Click **Actions → Send Activation Email**
   - User will receive 6-digit code via email

### System Validation Checklist
Before going live, verify:
- [ ] At least one project created and active
- [ ] Administrative hierarchy complete (Country → Province → District)
- [ ] All essential issue statuses created (Open, Assigned, In Progress, Resolved, Closed)
- [ ] Issue categories match your departments
- [ ] Issue types cover common scenarios
- [ ] Age groups and citizen groups configured
- [ ] User accounts created with proper roles
- [ ] Project assignments completed
- [ ] Activation emails sent to government workers
- [ ] Test issue creation works end-to-end

---

## Project Manager Guide

### Daily Project Management Tasks

#### Dashboard Overview
Your **GRM Project Manager** workspace shows:
- **Project Issues**: All issues in your projects
- **Open Issues**: Currently active issues
- **User Assignments**: Team member assignments
- **Escalated Issues**: Issues requiring attention

#### Managing Your Project Team

1. **Review Team Assignments**
   - Go to: **User Assignments** (filtered to your projects)
   - Check that all roles are filled:
     - Department Heads for each major department
     - Field Officers for each region
     - Adequate coverage for expected issue volume

2. **Add New Team Members**
   - Go to: **GRM User Project Assignment → New**
   - Assign users to your project with appropriate roles
   - Set regional restrictions if needed
   - Send activation codes for government workers

3. **Monitor Team Performance**
   - Review **Project Issues** regularly
   - Check resolution times by assignee
   - Identify officers with high workloads
   - Reassign issues if needed

#### Issue Management Workflows

1. **Daily Issue Review**
   - Check **Open Issues** shortcut
   - Review unassigned issues
   - Monitor escalated issues
   - Approve complex resolutions

2. **Assignment Strategy**
   - New issues auto-assign based on category settings
   - Manually assign complex or sensitive issues
   - Balance workload across team members
   - Consider regional expertise

3. **Escalation Handling**
   - Review **Escalated Issues** daily
   - Determine escalation validity
   - Reassign to specialists if needed
   - Escalate to administrators when necessary

#### Project Configuration Management

1. **Update Categories and Types**
   - Add new categories as issues arise
   - Modify department assignments
   - Update redirection protocols
   - Ensure categories stay current

2. **Regional Coverage**
   - Monitor **Administrative Regions**
   - Add new regions as project expands
   - Update field officer assignments
   - Ensure complete coverage

### Weekly Project Reports
Generate these reports weekly:
1. **Issue Volume Trends**: Track new vs. resolved issues
2. **Team Performance**: Resolution times by assignee
3. **Category Analysis**: Most common issue types
4. **Regional Distribution**: Issues by administrative region
5. **Citizen Feedback**: Satisfaction ratings and comments

---

## Department Head Guide

### Setting Up Your Department

#### Initial Department Configuration
1. **Verify Department Record**
   - Go to: **GRM Issue Department**
   - Find your department
   - Ensure you're listed as the **Head**
   - Verify project links are correct

2. **Review Assigned Categories**
   - Go to: **GRM Issue Category**
   - Find categories assigned to your department
   - Verify redirection protocols are appropriate
   - Request changes if needed

#### Team Management

1. **Know Your Field Officers**
   - Go to: **User Assignments**
   - Filter by your department
   - Review regional assignments
   - Contact each officer to establish communication

2. **Establish Standard Procedures**
   - Define response time expectations
   - Create issue investigation guidelines
   - Establish escalation criteria
   - Set quality standards for resolutions

### Daily Operations

#### Morning Routine
1. **Check New Assignments**
   - Review issues assigned to your department overnight
   - Prioritize urgent or complex issues
   - Assign to appropriate field officers

2. **Review Escalated Issues**
   - Check issues escalated by field officers
   - Determine next steps
   - Reassign or take personal ownership as needed

#### Issue Assignment Process

1. **Evaluate New Issues**
   - Read issue description carefully
   - Consider complexity and required expertise
   - Check regional factors
   - Review citizen type (confidential issues need special handling)

2. **Assign to Field Officers**
   - Open the issue record
   - Set **Assignee** field to chosen officer
   - Add assignment comment explaining priority/approach
   - Save the issue

3. **Set Expectations**
   - Contact officer if urgent
   - Provide additional context if needed
   - Set follow-up schedule

#### Quality Control

1. **Review Resolutions**
   - Check resolved issues before citizen notification
   - Verify solution appropriateness
   - Ensure proper documentation
   - Approve or request revisions

2. **Monitor Resolution Times**
   - Track time from assignment to resolution
   - Identify delays and bottlenecks
   - Provide support where needed
   - Adjust assignments if necessary

### Weekly Department Review
1. **Team Performance Meeting**
   - Review departmental statistics
   - Discuss challenging cases
   - Share best practices
   - Plan improvements

2. **Process Improvements**
   - Identify recurring issue types
   - Develop standard solutions
   - Update procedures as needed
   - Train team on new approaches

---

## Field Officer Guide

### Getting Started

#### First Login
1. **Access the System**
   - Go to: https://egrm.local
   - Use your email and initial password
   - If first time, you'll need activation code from email

2. **Complete Activation**
   - Enter 6-digit code from email
   - Set your new password
   - Complete profile if prompted

3. **Explore Your Workspace**
   - **GRM Field Officer** workspace loads automatically
   - Review shortcuts: New Issue, My Issues, In Progress
   - Familiarize yourself with navigation

#### Understanding Your Assignment
1. **Check Your Assignment**
   - Go to: **User Assignments**
   - Note your assigned project and region
   - Understand your geographical coverage
   - Contact supervisor if unclear

2. **Learn Your Region**
   - Go to: **Administrative Regions**
   - Study your assigned region's hierarchy
   - Understand sub-regions you cover
   - Note important locations

### Creating New Issues

#### Information Gathering
Before creating an issue, gather:
- **Citizen Information**: Name, age group, contact details
- **Issue Details**: What happened, when, where
- **Evidence**: Photos, documents, witness information
- **Location**: Specific administrative region and GPS if possible

#### Issue Creation Process

1. **Start New Issue**
   - Click **"New Issue"** shortcut on dashboard
   - Or go to: **GRM Issue → New**

2. **Fill Issue Details Section**
   ```
   Title: [Brief, clear description - max 50 characters]
   Example: "Water pump broken in Muhanga Cell"

   Description: [Detailed explanation]
   Example: "Community water pump has been non-functional for 3 days.
   Pump motor appears damaged. Approximately 150 households affected.
   Citizens report no water access since June 4th."

   Status: Open (should auto-populate)
   Project: [Your assigned project]
   Category: [Choose most appropriate - e.g., "Water Supply Issues"]
   Issue Type: [Usually "Complaint" for problems, "Request for Service" for new needs]
   ```

3. **Set Location Information**
   ```
   Administrative Region: [Select most specific region - usually Cell level]
   Intake Date: [Today's date]
   Issue Date: [When problem actually occurred]
   Issue Location: [Add GPS coordinates if available]
   ```

4. **Enter Citizen Information**
   ```
   Citizen Type:
   - 0=Visible (citizen OK with name being public)
   - 1=Confidential (citizen wants anonymity)
   - 2=Individual Proxy (you're reporting for someone)
   - 3=Organization Proxy (reporting for group)

   Citizen: [Full name if type 0 or 2/3]
   Citizen (Confidential): [Use if type 1]

   Gender: [Male/Female/Other/Rather not say]

   Contact Medium:
   - anonymous (no contact info)
   - facilitator (contact through you)
   - contact (direct citizen contact)

   Contact Information: [Phone/email if "contact" selected]
   Citizen Age Group: [Select appropriate age range]
   Citizen Group 1 & 2: [Select demographic categories if applicable]
   ```

5. **Save the Issue**
   - Click **Save**
   - System generates tracking code automatically
   - Note the tracking code for citizen reference

### Managing Your Assigned Issues

#### Daily Issue Review

1. **Check "My Issues"**
   - Click **"My Issues"** shortcut
   - Review all issues assigned to you
   - Prioritize by urgency and complexity

2. **Update Issue Status**
   - When you start working: Change status to **"In Progress"**
   - When resolved: Change to **"Resolved"**
   - Add comments explaining your actions

#### Investigation Process

1. **Visit the Site**
   - Go to the location mentioned in issue
   - Take photos of the problem
   - Interview affected citizens
   - Gather additional evidence

2. **Document Your Findings**
   - Go to the issue record
   - Scroll to **Comments** section
   - Click **Add Row**
   - Enter detailed findings:
   ```
   Example comment:
   "Site visit completed 2025-06-07. Confirmed water pump motor burned out.
   Local technician estimates repair cost at 150,000 RWF. Temporary water
   source available 500m away. Recommended immediate repair through district
   maintenance budget."
   ```

3. **Add Attachments**
   - Scroll to **Attachments** section
   - Click **Add Row**
   - Upload photos or documents
   - Add descriptions for each file

#### Resolution Process

1. **Coordinate Solution**
   - Contact relevant departments/agencies
   - Arrange repairs or services
   - Follow up on implementation
   - Keep citizen informed

2. **Document Resolution**
   - Update issue status to **"Resolved"**
   - Add detailed resolution comment:
   ```
   Example:
   "Issue resolved 2025-06-09. District maintenance team repaired pump motor.
   Water service restored to full capacity. Tested with community members.
   Provided maintenance schedule to local water committee."
   ```

3. **Follow Up**
   - Contact citizen to confirm satisfaction
   - Update **Resolution Accepted** field if citizen confirms
   - Request rating if citizen feedback enabled

### Escalation Guidelines

#### When to Escalate
Escalate issues when:
- Solution requires resources beyond your authority
- Technical expertise needed that you don't have
- Inter-departmental coordination required
- Citizen dissatisfied with initial resolution
- Issue involves policy decisions
- Timeline exceeds department standards

#### How to Escalate

1. **Set Escalation Flag**
   - Open the issue
   - Check **Escalate Flag** box
   - Save the issue

2. **Add Escalation Reason**
   - Scroll to **Escalation** section
   - Click **Add Row** in Escalation Reasons table
   - Enter detailed reason:
   ```
   Example:
   "Escalating to department head. Issue requires approval for emergency
   budget allocation of 500,000 RWF for pump replacement. Local repair
   not possible due to obsolete parts."
   ```

3. **Notify Supervisor**
   - Contact your department head directly
   - Provide issue tracking code
   - Explain urgency level

### Working with Citizens

#### Communication Best Practices
1. **Professional Approach**
   - Always be respectful and patient
   - Listen carefully to citizen concerns
   - Ask clarifying questions
   - Explain the process clearly

2. **Setting Expectations**
   - Explain what you can and cannot do
   - Provide realistic timelines
   - Give them the tracking code
   - Explain how they'll be updated

3. **Confidentiality**
   - Respect citizen privacy choices
   - Handle confidential issues with extra care
   - Don't share details with unauthorized people
   - Use secure channels for sensitive information

#### Providing Updates
1. **Regular Communication**
   - Contact citizen at key milestones
   - Explain any delays or complications
   - Ask for additional information if needed

2. **Final Resolution**
   - Explain what was done
   - Verify citizen satisfaction
   - Provide information for future reference
   - Request feedback if appropriate

---

## User Management

### Role-Based Access Control

#### Role Capabilities Summary

| Capability | GRM Admin | Project Manager | Dept Head | Field Officer | Analyst |
|------------|-----------|-----------------|-----------|---------------|---------|
| Create Projects | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create Users | ✅ | ❌ | ❌ | ❌ | ❌ |
| Assign Users to Projects | ✅ | ✅ | ❌ | ❌ | ❌ |
| Create Issues | ✅ | ✅ | ✅ | ✅ | ❌ |
| Assign Issues | ✅ | ✅ | ✅ | ❌ | ❌ |
| Resolve Issues | ✅ | ✅ | ✅ | ✅ | ❌ |
| View All Issues | ✅ | Project Only | Dept Only | Assigned Only | Read Only |
| Configure Categories | ✅ | ✅ | ❌ | ❌ | ❌ |
| Generate Reports | ✅ | ✅ | ✅ | ❌ | ✅ |

### User Account Management

#### Creating New Users

1. **Standard User Creation**
   - Go to: **Users → New User**
   - Fill required information:
   ```
   Email: [Must be unique]
   First Name: [Given name]
   Last Name: [Family name]
   Full Name: [Display name]
   Send Welcome Email: ✅ (recommended)
   ```

2. **Government Worker Setup**
   - Create user account first
   - Then create **GRM User Project Assignment**
   - System generates activation code automatically
   - User receives email with activation instructions

#### Password and Security

1. **Initial Passwords**
   - System generates temporary password
   - Sent via welcome email
   - User must change on first login

2. **Government Worker Activation**
   - 6-digit activation code sent via email
   - Code expires in 7 days
   - Maximum 5 activation attempts
   - Can resend code if needed

3. **Password Reset**
   - Users can reset via "Forgot Password" link
   - Administrators can reset from user record
   - Strong password requirements enforced

### Project Assignment Guidelines

#### Assignment Best Practices

1. **Regional Coverage**
   - Assign field officers to specific regions
   - Ensure no gaps in coverage
   - Consider geographical accessibility
   - Plan for backup coverage

2. **Workload Balance**
   - Monitor issue volume per officer
   - Adjust assignments based on capacity
   - Consider officer expertise
   - Rotate assignments to build skills

3. **Department Structure**
   - Each department needs at least one head
   - Field officers should align with department focus
   - Cross-training for flexibility
   - Clear escalation paths

#### Managing Inactive Users

1. **Deactivating Assignments**
   - Go to **GRM User Project Assignment**
   - Uncheck **Is Active** for leaving users
   - Reassign their open issues
   - Update regional coverage

2. **Account Suspension**
   - For security issues or policy violations
   - Set **Enabled** to unchecked in User record
   - Document reason for audit trail
   - Notify affected supervisors

---

## Troubleshooting

### Common Setup Issues

#### "User Cannot See Issues"
**Symptoms**: User logs in but sees no issues in their list
**Causes & Solutions**:

1. **No Project Assignment**
   - Check: Go to **GRM User Project Assignment**
   - Look for user's email
   - Solution: Create assignment if missing

2. **Inactive Assignment**
   - Check: **Is Active** field in assignment
   - Solution: Check the **Is Active** box

3. **Wrong Role**
   - Check: **Role** field in assignment
   - Solution: Change to appropriate role (GRM Field Officer, etc.)

4. **No Regional Access**
   - Check: **Administrative Region** in assignment
   - Solution: Assign appropriate region

#### "Activation Code Not Working"
**Symptoms**: Government worker cannot activate account
**Causes & Solutions**:

1. **Code Expired**
   - Check: **Activation Expires On** in assignment
   - Solution: Click **Actions → Resend Activation Code**

2. **Too Many Attempts**
   - Check: **Activation Attempts** field
   - Solution: Reset attempts to 0, resend code

3. **Wrong Email**
   - Check: Email in user account vs. assignment
   - Solution: Ensure emails match exactly

#### "Categories Not Showing"
**Symptoms**: No categories available when creating issues
**Causes & Solutions**:

1. **No Project Link**
   - Check: **Project Link** table in category
   - Solution: Add row with correct project

2. **Wrong Project**
   - Check: Project in category vs. user's assignment
   - Solution: Ensure projects match

#### "Permission Denied Errors"
**Symptoms**: User gets "No permission" errors
**Causes & Solutions**:

1. **Role Not Assigned**
   - Check: **Roles** section in User record
   - Solution: Add appropriate GRM role

2. **Role Not in Assignment**
   - Check: **Role** field in project assignment
   - Solution: Set to correct GRM role

### Data Integrity Issues

#### "Broken Hierarchy"
**Symptoms**: Regions showing incorrect relationships
**Solutions**:
1. Check **Parent Region** fields for circular references
2. Ensure **Administrative Level** sequence is logical
3. Verify **Path** field auto-generation

#### "Missing Lookup Data"
**Symptoms**: Dropdowns showing "No items found"
**Solutions**:
1. Verify at least one record exists for each lookup type
2. Check **Project Link** tables in classification records
3. Ensure project is **Active**

### Performance Issues

#### "Slow Loading"
**Symptoms**: System responses are slow
**Solutions**:
1. Check database indexes on commonly filtered fields
2. Archive old resolved issues
3. Optimize browser cache settings
4. Monitor server resource usage

#### "Search Not Working"
**Symptoms**: Cannot find records that should exist
**Solutions**:
1. Check search field configuration
2. Verify **Index Web Pages for Search** is enabled
3. Rebuild search index if needed

### Best Practices for Administrators

#### Regular Maintenance Tasks

1. **Weekly**
   - Review new user registrations
   - Check for failed activation attempts
   - Monitor issue resolution times
   - Backup critical configuration data

2. **Monthly**
   - Archive resolved issues older than 6 months
   - Review user access assignments
   - Update regional coverage as needed
   - Generate system usage reports

3. **Quarterly**
   - Review and update categories/types
   - Audit user permissions
   - Plan capacity for expected growth
   - Update documentation and procedures

#### Monitoring Key Metrics

1. **User Activity**
   - Login frequency by role
   - Issue creation rates
   - Resolution time averages
   - Escalation rates

2. **System Health**
   - Database size growth
   - API response times
   - Error log frequencies
   - Storage usage trends

3. **Data Quality**
   - Incomplete issue records
   - Orphaned assignments
   - Duplicate categories
   - Broken region hierarchies

---

## Quick Reference Cards

### For New Administrators
```
Setup Sequence:
1. Create Administrative Level Types
2. Create first Project
3. Create Administrative Regions (top-down)
4. Create Departments
5. Create Issue Statuses (Open, Assigned, In Progress, Resolved, Closed)
6. Create Issue Categories (linked to departments)
7. Create Issue Types
8. Create Age Groups and Citizen Groups
9. Create User accounts
10. Create Project Assignments
11. Send activation codes
```

### For Project Managers
```
Daily Tasks:
□ Check Open Issues shortcut
□ Review Escalated Issues
□ Monitor team performance
□ Assign unassigned issues
□ Approve complex resolutions

Weekly Tasks:
□ Generate project reports
□ Review team workload
□ Update project configuration
□ Plan resource allocation
```

### For Department Heads
```
Daily Tasks:
□ Review new department issues
□ Assign to field officers
□ Check escalated issues
□ Approve resolutions

Quality Checklist:
□ Complete investigation documented
□ Appropriate solution provided
□ Citizen notification completed
□ Proper categorization used
```

### For Field Officers
```
Creating Issues:
1. Gather complete information
2. Choose specific region
3. Select appropriate category
4. Enter citizen details carefully
5. Add photos/documents
6. Save and note tracking code

Resolution Process:
1. Change status to "In Progress"
2. Investigate thoroughly
3. Document findings in comments
4. Coordinate solution
5. Update to "Resolved"
6. Confirm with citizen
```

---

*This guide covers the essential setup and usage procedures for EGRM. For additional support, contact your system administrator or refer to the complete technical documentation.*
