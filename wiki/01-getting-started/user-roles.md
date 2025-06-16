# User Roles and Permissions

Understanding user roles is essential for effective use of the EGRM system. Each role has specific permissions and responsibilities designed to ensure proper workflow and data security.

## 🏗️ Role Hierarchy

The EGRM system uses a hierarchical role structure:

```
System Manager (Frappe Built-in)
├── GRM Administrator
├── GRM Project Manager
├── GRM Department Head
├── GRM Field Officer
└── GRM Analyst
```

## 👤 Role Descriptions

### System Manager
**Built-in Frappe role with complete system access**

**Responsibilities:**
- Overall system administration
- Technical configuration
- User account management
- System security and backups

**Key Capabilities:**
- Full access to all EGRM functions
- Frappe system administration
- Database management
- System configuration

**Who Gets This Role:**
- System administrators
- IT support staff
- Senior technical personnel

---

### GRM Administrator
**Complete EGRM system administration**

**Responsibilities:**
- EGRM system configuration
- Multi-project oversight
- Master data management
- User role assignments

**Key Capabilities:**
- Create and configure projects
- Manage all users and assignments
- Configure system-wide settings
- Access all issues across projects
- Generate system-wide reports

**Typical Tasks:**
- Initial system setup
- Creating new projects
- Managing user accounts
- Configuring categories and types
- System maintenance

**Who Gets This Role:**
- GRM program coordinators
- Senior administrators
- System owners

---

### GRM Project Manager
**Project-specific management and oversight**

**Responsibilities:**
- Project configuration and management
- Team coordination
- Project performance monitoring
- Stakeholder reporting

**Key Capabilities:**
- Manage assigned projects
- Configure project-specific settings
- Assign users to projects
- View all issues within projects
- Generate project reports

**Typical Tasks:**
- Setting up new projects
- Managing project team
- Monitoring project performance
- Coordinating with departments
- Reporting to stakeholders

**Who Gets This Role:**
- Project managers
- Program coordinators
- Regional supervisors

---

### GRM Department Head
**Department-level management and supervision**

**Responsibilities:**
- Departmental issue oversight
- Team supervision
- Quality control
- Resource allocation

**Key Capabilities:**
- View department-assigned issues
- Assign issues to field officers
- Approve resolutions
- Manage department team
- Generate department reports

**Typical Tasks:**
- Reviewing new issues
- Assigning work to field officers
- Approving complex resolutions
- Managing team workload
- Handling escalations

**Who Gets This Role:**
- Department directors
- Division heads
- Team leaders
- Senior supervisors

---

### GRM Field Officer
**Frontline issue handling and resolution**

**Responsibilities:**
- Direct citizen interaction
- Issue investigation and resolution
- Data collection and documentation
- Field work execution

**Key Capabilities:**
- Create new issues
- Manage assigned issues
- Update issue status
- Add comments and attachments
- Submit resolutions

**Typical Tasks:**
- Creating issues from citizen reports
- Investigating assigned issues
- Implementing solutions
- Documenting activities
- Communicating with citizens

**Who Gets This Role:**
- Field officers
- Community liaisons
- Customer service representatives
- Frontline staff

---

### GRM Analyst
**Reporting and data analysis (read-only)**

**Responsibilities:**
- Data analysis and reporting
- Performance monitoring
- Trend identification
- Report generation

**Key Capabilities:**
- View issues (read-only)
- Generate reports
- Export data
- Access analytics dashboards
- View system statistics

**Typical Tasks:**
- Creating performance reports
- Analyzing trends
- Monitoring KPIs
- Supporting decision-making
- Data quality assessment

**Who Gets This Role:**
- Data analysts
- Monitoring & evaluation staff
- Research personnel
- Reporting specialists

## 📊 Permission Matrix

| Capability | System Manager | GRM Admin | Project Manager | Dept Head | Field Officer | Analyst |
|------------|----------------|-----------|-----------------|-----------|---------------|---------|
| **System Administration** |
| Create Projects | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage System Settings | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Create User Accounts | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Assign Users to Projects | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Issue Management** |
| Create Issues | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View All Issues | ✅ | ✅ | Project Only | Dept Only | Assigned Only | Read Only |
| Assign Issues | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Resolve Issues | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Delete Issues | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Configuration** |
| Manage Categories | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage Issue Types | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage Statuses | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Manage Regions | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **Reporting** |
| Generate System Reports | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Generate Project Reports | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| Generate Department Reports | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Export Data | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |

## 🏢 Workspace Configurations

Each role has a customized workspace showing relevant shortcuts and information:

### GRM Administrator Workspace
- **Quick Access**: All Issues, Projects, Categories, Departments
- **Administration**: User Assignments, Administrative Regions, Level Types
- **Configuration**: Issue Types, Statuses, Citizen Groups, Age Groups
- **Reports**: System-wide analytics and reports

### GRM Project Manager Workspace
- **Project Management**: Project Issues, My Projects, Categories, Departments
- **Team Management**: User Assignments, Administrative Regions
- **Configuration**: Types, Statuses, Citizen Groups, Age Groups
- **Reports**: Project-specific analytics and reports

### GRM Department Head Workspace
- **Issue Management**: Department Issues, Assigned Issues, Unassigned Issues
- **Team Oversight**: Field Officer Performance, Workload Distribution
- **Quality Control**: Pending Approvals, Resolution Reviews
- **Reports**: Department performance and statistics

### GRM Field Officer Workspace
- **My Work**: Assigned Issues, In Progress Issues, New Assignments
- **Regional Work**: Regional Issues, Unassigned Regional Issues
- **Tools**: New Issue Creation, Issue Search, Quick Actions
- **Status**: My Performance, Pending Tasks

### GRM Analyst Workspace
- **Dashboards**: System Analytics, Project Performance, Trend Analysis
- **Reports**: Standard Reports, Custom Report Builder
- **Data**: Export Tools, Data Quality Checks
- **Monitoring**: KPI Tracking, Alert Management

## 🔐 Security Considerations

### Access Control Principles
- **Least Privilege**: Users get only the minimum access needed for their role
- **Project Isolation**: Users can only access their assigned projects
- **Regional Restrictions**: Field officers limited to their assigned regions
- **Data Sensitivity**: Confidential data requires special permissions

### Permission Inheritance
- Higher-level roles inherit permissions from lower levels
- Project-specific permissions override system defaults
- Regional assignments limit data visibility
- Department assignments control issue routing

## 📝 Role Assignment Process

### For Administrators
1. Create user account (if needed)
2. Assign appropriate role in user profile
3. Create project assignment
4. Set regional/departmental restrictions
5. Send activation credentials (for government workers)

### For Users
1. Receive activation email with credentials
2. Login and activate account (government workers)
3. Complete profile information
4. Explore role-specific workspace
5. Begin role-specific training

## 🎯 Best Practices

### Role Assignment Guidelines
- **Match Skills**: Assign roles that match user skills and responsibilities
- **Clear Boundaries**: Ensure users understand their role limitations
- **Regular Review**: Periodically review and update role assignments
- **Training**: Provide role-specific training for all users
- **Documentation**: Maintain clear records of role assignments

### Security Best Practices
- **Regular Audits**: Review user access regularly
- **Prompt Removal**: Remove access for users who leave
- **Strong Authentication**: Enforce strong password policies
- **Activity Monitoring**: Monitor user activity for anomalies
- **Data Classification**: Handle confidential data appropriately

## 🆘 Getting Help

### Role-Specific Support
- **System Issues**: Contact System Manager or GRM Administrator
- **Role Questions**: Contact your immediate supervisor
- **Training Needs**: Request role-specific training materials
- **Access Issues**: Contact the administrator who assigned your role

### Escalation Path
1. **Immediate Supervisor**: For operational questions
2. **Project Manager**: For project-related issues
3. **GRM Administrator**: For system access problems
4. **System Manager**: For technical issues

## 📚 Next Steps

Based on your role, proceed to the appropriate guide:

- **GRM Administrator**: [Administrator Guides](../02-administrator-guides/)
- **GRM Project Manager**: [Project Manager Guides](../03-project-manager-guides/)
- **GRM Department Head**: [Department Head Guides](../04-department-head-guides/)
- **GRM Field Officer**: [Field Officer Guides](../05-field-officer-guides/)
- **GRM Analyst**: Contact your supervisor for analyst-specific training

Or continue with the general getting started materials:
- [Basic Concepts](./basic-concepts.md)
- [Navigation Guide](./navigation.md)