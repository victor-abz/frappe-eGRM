# Basic Concepts and Terminology

Understanding the key concepts and terminology used in EGRM is essential for effective system use. This page explains the fundamental concepts that you'll encounter throughout the system.

## 🎯 Core Concepts

### Issue
**Definition**: A citizen's grievance, complaint, request for service, or feedback about a government project or service.

**Key Points**:
- Central entity in the EGRM system
- Each issue receives a unique tracking code
- Issues progress through defined statuses
- Can include attachments, comments, and location data

**Examples**:
- "Water pump broken in Muhanga Cell"
- "Request for new school in district"
- "Complaint about road condition"
- "Suggestion for improved service delivery"

### Project
**Definition**: A specific GRM implementation with its own configuration, team, and coverage area.

**Key Points**:
- Multiple projects can run simultaneously
- Each project has independent settings
- Projects can cover different geographical areas
- Project-specific user assignments and permissions

**Examples**:
- "Rwanda National GRM 2025"
- "Kigali City Infrastructure GRM"
- "Health Services Feedback System"

### Assignment
**Definition**: The linking of users to projects with specific roles and responsibilities.

**Key Points**:
- Defines what users can access
- Includes role, project, and regional restrictions
- Controls permissions and visibility
- Can include activation requirements for government workers

### Administrative Region
**Definition**: Geographical administrative boundaries used for organizing and routing issues.

**Key Points**:
- Hierarchical structure (Country → Province → District → Sector → Cell)
- Used for automatic issue routing
- Determines field officer assignments
- Supports location-based reporting

### Status
**Definition**: The current state of an issue in the resolution workflow.

**Common Statuses**:
- **Open**: New issue, not yet assigned
- **Assigned**: Assigned to a field officer
- **In Progress**: Actively being worked on
- **Resolved**: Solution implemented
- **Closed**: Issue complete, citizen satisfied
- **Rejected**: Issue not valid or actionable

### Category
**Definition**: Subject matter classification for issues (what the issue is about).

**Key Points**:
- Links to responsible departments
- Determines assignment routing
- Used for reporting and analysis
- Project-specific configuration

**Examples**:
- Infrastructure Issues
- Health Services
- Education Services
- Environmental Concerns
- Social Services

### Issue Type
**Definition**: The nature or type of the citizen's interaction.

**Common Types**:
- **Complaint**: Problem that needs fixing
- **Request for Service**: New service needed
- **Suggestion**: Improvement recommendation
- **Information Request**: Seeking information
- **Appeal**: Challenging a previous decision

## 👥 User and Access Concepts

### User Roles
**Definition**: Predefined sets of permissions and responsibilities within the system.

**Role Types**:
- **GRM Administrator**: System-wide management
- **GRM Project Manager**: Project oversight
- **GRM Department Head**: Department management
- **GRM Field Officer**: Direct issue handling
- **GRM Analyst**: Reporting and analysis

### Activation
**Definition**: The process of activating government worker accounts using email-sent activation codes.

**Key Points**:
- 6-digit codes sent via email
- Required for department heads and field officers
- Codes expire in 7 days
- Maximum 5 attempts allowed

### Permissions
**Definition**: Specific actions that users can or cannot perform in the system.

**Permission Types**:
- **Read**: View information
- **Write**: Modify existing records
- **Create**: Add new records
- **Delete**: Remove records
- **Submit**: Finalize records

## 📊 Classification Concepts

### Citizen Type
**Definition**: Controls the visibility and handling of citizen information.

**Types**:
- **0 = Visible**: Citizen name can be public
- **1 = Confidential**: Citizen identity protected
- **2 = Individual Proxy**: Officer reporting for individual
- **3 = Organization Proxy**: Officer reporting for group

### Contact Medium
**Definition**: How the citizen can be contacted for follow-up.

**Options**:
- **anonymous**: No contact information provided
- **facilitator**: Contact through the reporting officer
- **contact**: Direct contact with citizen

### Age Group
**Definition**: Citizen age classifications for demographic analysis.

**Typical Groups**:
- Child (0-17)
- Young Adult (18-30)
- Adult (31-60)
- Senior (60+)

### Citizen Groups
**Definition**: Demographic classifications for analysis and targeting.

**Group Type 1** (Primary Demographics):
- Women, Men, Youth, Elderly, Disabled

**Group Type 2** (Occupation/Social):
- Farmers, Traders, Students, Civil Servants, Unemployed

## 🔄 Workflow Concepts

### Escalation
**Definition**: Moving an issue to a higher level of authority when standard resolution isn't sufficient.

**Escalation Triggers**:
- Time limits exceeded
- Citizen dissatisfaction
- Resource requirements beyond officer authority
- Technical complexity
- Policy implications

### Resolution
**Definition**: The solution or action taken to address the citizen's issue.

**Resolution Process**:
1. Investigation and analysis
2. Solution implementation
3. Documentation of actions taken
4. Citizen notification
5. Confirmation of satisfaction

### Tracking Code
**Definition**: Unique identifier given to citizens for tracking their issues.

**Characteristics**:
- Human-readable format
- Unique across the system
- Used for citizen communication
- Enables status checking

## 📍 Location Concepts

### Hierarchical Path
**Definition**: The complete administrative path from country to specific location.

**Example**: Rwanda → Kigali Province → Nyarugenge District → Nyarugenge Sector → Nyakabanda Cell

### GPS Coordinates
**Definition**: Precise geographical location where the issue occurred.

**Uses**:
- Accurate location identification
- Mapping and spatial analysis
- Field officer navigation
- Resource planning

## 📈 Reporting Concepts

### Performance Metrics
**Definition**: Quantitative measures used to assess system and user performance.

**Key Metrics**:
- Issue volume (new issues per period)
- Resolution time (average days to resolve)
- Resolution rate (percentage resolved)
- Citizen satisfaction (ratings and feedback)
- Escalation rate (percentage escalated)

### Dashboard
**Definition**: Visual interface showing key metrics and status information.

**Dashboard Types**:
- **Personal**: Individual user performance
- **Departmental**: Department-level metrics
- **Project**: Project-wide statistics
- **System**: Overall system performance

## 🔗 Technical Concepts

### DocType
**Definition**: Frappe framework term for data structures or "tables" in the system.

**Key DocTypes in EGRM**:
- GRM Issue
- GRM Project
- GRM User Project Assignment
- GRM Administrative Region
- GRM Issue Category

### Child Table
**Definition**: Related data that belongs to a main record.

**Examples**:
- Issue Attachments (belong to an Issue)
- Issue Comments (belong to an Issue)
- Issue Logs (belong to an Issue)

### Link Field
**Definition**: Fields that reference other records in the system.

**Examples**:
- Issue → Project (links to GRM Project)
- Issue → Status (links to GRM Issue Status)
- Assignment → User (links to User)

## 🛡️ Security Concepts

### Confidentiality Levels
**Definition**: Controls who can access sensitive information.

**Levels**:
- **Public**: Standard visibility
- **Confidential**: Restricted access
- **Internal**: Organization-only access

### Data Sensitivity
**Definition**: Classification of information based on protection requirements.

**Types**:
- **Personal Information**: Citizen names, contact details
- **Location Data**: Precise geographical coordinates
- **Resolution Details**: Sensitive solution information
- **Internal Communications**: Staff comments and discussions

## 📱 Mobile Concepts

### Synchronization
**Definition**: Process of keeping mobile app data in sync with the main system.

**Sync Types**:
- **Full Sync**: Download all accessible data
- **Delta Sync**: Download only changes since last sync
- **Upload Sync**: Send local changes to server

### Offline Mode
**Definition**: Ability to work without internet connection.

**Offline Capabilities**:
- Create new issues
- Update existing issues
- Add photos and comments
- Record GPS locations

## 📋 Data Quality Concepts

### Validation
**Definition**: Rules that ensure data entered meets quality standards.

**Validation Types**:
- **Required Fields**: Must be filled
- **Format Validation**: Correct format (email, phone)
- **Range Validation**: Within acceptable limits
- **Relationship Validation**: Valid references

### Data Integrity
**Definition**: Accuracy and consistency of data throughout the system.

**Integrity Measures**:
- Referential integrity (valid links)
- Business rule enforcement
- Audit trail maintenance
- Regular data quality checks

## 🗓️ Temporal Concepts

### Intake Date
**Definition**: When the issue was first received by the system.

### Issue Date
**Definition**: When the actual problem occurred (may be different from intake date).

### Resolution Date
**Definition**: When the issue was marked as resolved.

### Created Date
**Definition**: System timestamp when the record was created.

## 🔄 Status Flags

### Initial Status
**Definition**: Status automatically assigned to new issues.

### Final Status
**Definition**: Status indicating the issue is complete.

### Open Status
**Definition**: Status indicating active work is happening.

### Rejected Status
**Definition**: Status indicating the issue was not accepted.

## 📊 Audit and Compliance

### Audit Trail
**Definition**: Complete record of all actions taken on an issue.

**Includes**:
- Who performed each action
- When actions were taken
- What changes were made
- Comments and justifications

### Compliance Tracking
**Definition**: Monitoring adherence to standards and procedures.

**Compliance Areas**:
- Response time standards
- Data protection requirements
- Resolution quality standards
- Citizen notification requirements

## 🎓 Learning and Training

### Role-Based Training
**Definition**: Training materials specific to each user role.

### Progressive Disclosure
**Definition**: Revealing system complexity gradually as users become more experienced.

### Best Practices
**Definition**: Proven methods for effective system use.

## 📚 Reference Materials

### Glossary
**Definition**: Alphabetical list of terms and definitions.

### Quick Reference Cards
**Definition**: Summarized procedures for common tasks.

### Standard Operating Procedures
**Definition**: Step-by-step instructions for key processes.

## 🆘 Getting Help

### Context-Sensitive Help
**Definition**: Help information specific to what you're currently doing.

### Escalation Procedures
**Definition**: Who to contact for different types of problems.

### Knowledge Base
**Definition**: Searchable collection of answers to common questions.

## 🎯 Key Takeaways

1. **Issues are Central**: Everything revolves around citizen issues
2. **Hierarchy Matters**: Both organizational and geographical hierarchies drive the system
3. **Roles Define Access**: Your role determines what you can see and do
4. **Process is Important**: Following proper workflows ensures quality
5. **Data Quality Counts**: Accurate, complete data improves outcomes
6. **Security is Built-in**: Multiple layers protect sensitive information

## 📚 Next Steps

Now that you understand the basic concepts, you're ready to:

1. **Learn Navigation**: [Navigation Guide](./navigation.md)
2. **Start Role Training**: Choose your role-specific guide
3. **Practice**: Use a test environment to practice
4. **Get Support**: Contact your supervisor or administrator

**Role-Specific Guides**:
- [Administrator Guides](../02-administrator-guides/)
- [Project Manager Guides](../03-project-manager-guides/)
- [Department Head Guides](../04-department-head-guides/)
- [Field Officer Guides](../05-field-officer-guides/)

---

*Understanding these concepts will help you use EGRM effectively and contribute to better service delivery for citizens.*