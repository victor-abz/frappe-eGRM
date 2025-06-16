# Initial System Setup

This guide walks you through setting up EGRM from scratch. Follow these steps in order to ensure proper system configuration.

## 🎯 Setup Overview

The initial setup involves these main phases:
1. **Administrative Structure**: Create geographical hierarchy
2. **Project Creation**: Set up your first project
3. **Classification System**: Configure categories, types, and statuses
4. **User Setup**: Create accounts and assignments
5. **Validation**: Test the complete workflow

## ⏱️ Estimated Time
- **Planning**: 2-4 hours
- **Configuration**: 4-8 hours  
- **Testing**: 2-4 hours
- **Total**: 1-2 days

## 📋 Pre-Setup Checklist

Before starting, ensure you have:
- [ ] Administrator access to EGRM system
- [ ] List of administrative regions and hierarchy
- [ ] Project requirements and scope
- [ ] User list with roles and contact information
- [ ] Department structure and responsibilities
- [ ] Categories and types to be supported

## 🏗️ Phase 1: Administrative Structure

### Step 1.1: Create Administrative Level Types

**Purpose**: Define the hierarchy levels for your geographical structure.

1. **Navigate to GRM Administrative Level Type**
   - Go to: **Home → EGRM → GRM Administrative Level Type → New**

2. **Create hierarchy levels in order** (from highest to lowest):

   **Country Level:**
   ```
   Level Name: Country
   Level Order: 1
   Project: [Leave empty for now - will link after project creation]
   ```

   **Province Level:**
   ```
   Level Name: Province
   Level Order: 2
   Project: [Leave empty for now]
   ```

   **District Level:**
   ```
   Level Name: District
   Level Order: 3
   Project: [Leave empty for now]
   ```

   **Sector Level:**
   ```
   Level Name: Sector
   Level Order: 4
   Project: [Leave empty for now]
   ```

   **Cell Level:**
   ```
   Level Name: Cell
   Level Order: 5
   Project: [Leave empty for now]
   ```

3. **Save each level** before creating the next

**💡 Tip**: You can customize level names to match your country's administrative structure (e.g., State, County, Municipality, etc.)

### Step 1.2: Verify Administrative Levels

1. **Check the list view**: Go to **GRM Administrative Level Type** list
2. **Verify order**: Levels should be listed in correct hierarchical order
3. **Test uniqueness**: Each level name should be unique

## 🏢 Phase 2: Project Creation

### Step 2.1: Create Your First Project

1. **Navigate to GRM Project**
   - Go to: **Home → EGRM → GRM Project → New**

2. **Fill in project details:**
   ```
   Project Title: Rwanda National GRM 2025
   Project Code: RW-NGRM-2025
   Description: National Grievance and Redress Mechanism for Rwanda
   Start Date: [Today's date]
   End Date: [Project end date, if known]
   Is Active: ✅ (checked)
   Default Language: English
   Auto Escalation Days: 30
   Enable Citizen Feedback: ✅ (checked)
   ```

3. **Save the project**

**Important Notes**:
- **Project Code** must be unique and will be used for identification
- **Auto Escalation Days** determines when issues are automatically flagged for escalation
- **Enable Citizen Feedback** allows citizens to rate resolutions

### Step 2.2: Link Administrative Levels to Project

1. **Edit each Administrative Level Type**
2. **Set the Project field** to your newly created project
3. **Save each level**

## 🌍 Phase 3: Geographic Hierarchy

### Step 3.1: Create Country-Level Region

1. **Navigate to GRM Administrative Region**
   - Go to: **Home → EGRM → GRM Administrative Region → New**

2. **Create country record:**
   ```
   Region Name: Rwanda
   Administrative Level: Country
   Parent Region: [Leave empty - this is the top level]
   Project: RW-NGRM-2025
   Location: [Optional - add GPS coordinates if desired]
   ```

3. **Save the region**

### Step 3.2: Create Provincial Regions

Create records for each province:

**Example - Kigali Province:**
```
Region Name: Kigali Province
Administrative Level: Province  
Parent Region: Rwanda
Project: RW-NGRM-2025
Location: [Optional GPS coordinates]
```

**Repeat for all provinces:**
- Eastern Province
- Northern Province  
- Southern Province
- Western Province

### Step 3.3: Create District Regions

Create districts under each province:

**Example - Nyarugenge District:**
```
Region Name: Nyarugenge District
Administrative Level: District
Parent Region: Kigali Province
Project: RW-NGRM-2025
Location: [Optional GPS coordinates]
```

**Continue the hierarchy** down to Sectors and Cells as needed for your coverage area.

**💡 Planning Tip**: You don't need to create the entire hierarchy at once. Start with the regions where you'll be piloting and expand later.

## 🏛️ Phase 4: Departments and Classifications

### Step 4.1: Create Issue Departments

1. **Navigate to GRM Issue Department**
   - Go: **Home → EGRM → GRM Issue Department → New**

2. **Create essential departments:**

   **Infrastructure Department:**
   ```
   Department Name: Infrastructure & Public Works
   Head: [Select a user - can be added later]
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Other departments to create:**
   - Health Services
   - Education Services  
   - Social Services
   - Environmental Protection
   - Security & Safety

3. **Save each department**

### Step 4.2: Create Issue Statuses

Create the workflow statuses:

1. **Navigate to GRM Issue Status → New**

2. **Create these essential statuses:**

   **Initial Status:**
   ```
   Status Name: Open
   Initial Status: ✅ (checked)
   Open Status: ✅ (checked)
   Final Status: ❌ (unchecked)
   Rejected Status: ❌ (unchecked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Work Statuses:**
   ```
   Status Name: Assigned
   Initial Status: ❌ 
   Open Status: ✅ (checked)
   Final Status: ❌
   Rejected Status: ❌
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   ```
   Status Name: In Progress
   Initial Status: ❌
   Open Status: ✅ (checked)  
   Final Status: ❌
   Rejected Status: ❌
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Resolution Statuses:**
   ```
   Status Name: Resolved
   Initial Status: ❌
   Open Status: ❌
   Final Status: ✅ (checked)
   Rejected Status: ❌
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   ```
   Status Name: Closed
   Initial Status: ❌
   Open Status: ❌
   Final Status: ✅ (checked)
   Rejected Status: ❌
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Rejection Status:**
   ```
   Status Name: Rejected
   Initial Status: ❌
   Open Status: ❌
   Final Status: ✅ (checked)
   Rejected Status: ✅ (checked)
   Project Link: Add row → Project: RW-NGRM-2025
   ```

### Step 4.3: Create Issue Categories

Link categories to departments:

1. **Navigate to GRM Issue Category → New**

2. **Create categories matching your departments:**

   **Infrastructure Category:**
   ```
   Category Name: Infrastructure Issues
   Display Label: Infrastructure & Public Works
   Abbreviation: INFRA
   Assigned Department: Infrastructure & Public Works
   Confidentiality Level: Public
   Redirection Protocol: 0=Assign to head
   Administrative Level: [Select appropriate level]
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Other categories to create:**
   - Water Supply Issues (WATER) → Infrastructure & Public Works
   - Road Maintenance (ROADS) → Infrastructure & Public Works
   - Healthcare Access (HEALTH) → Health Services  
   - Education Quality (EDU) → Education Services
   - Social Welfare (SOCIAL) → Social Services
   - Environmental Concerns (ENV) → Environmental Protection

### Step 4.4: Create Issue Types

1. **Navigate to GRM Issue Type → New**

2. **Create general issue types:**

   ```
   Type Name: Complaint
   Project Link: Add row → Project: RW-NGRM-2025
   ```

   **Other types to create:**
   - Request for Service
   - Suggestion
   - Information Request
   - Appeal

### Step 4.5: Create Citizen Classifications

**Age Groups:**
1. Go to **GRM Issue Age Group → New**

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

**Citizen Groups:**
1. Go to **GRM Issue Citizen Group → New**

   **Primary Demographics (Group Type 1):**
   ```
   Group Name: Women
   Group Type: 1
   ```
   
   **Create:** Women, Men, Youth, Elderly, Disabled

   **Occupation/Social Groups (Group Type 2):**
   ```
   Group Name: Farmers
   Group Type: 2
   ```
   
   **Create:** Farmers, Traders, Students, Civil Servants, Unemployed

## 👥 Phase 5: User Setup

### Step 5.1: Create User Accounts

1. **Navigate to User → New User**

2. **Create accounts for each team member:**
   ```
   Email: john.doe@ministry.gov.rw
   First Name: John
   Last Name: Doe  
   Full Name: John Doe
   Send Welcome Email: ✅ (checked)
   ```

3. **Assign appropriate roles** in the Roles section:
   - GRM Administrator
   - GRM Project Manager  
   - GRM Department Head
   - GRM Field Officer
   - GRM Analyst

### Step 5.2: Create Project Assignments

1. **Navigate to GRM User Project Assignment → New**

2. **Create assignments for each user:**

   **Department Head Assignment:**
   ```
   User: john.doe@ministry.gov.rw
   Project: RW-NGRM-2025
   Role: GRM Department Head
   Department: Infrastructure & Public Works
   Administrative Region: [Select appropriate region]
   Is Active: ✅ (checked)
   Position Title: Director of Public Works
   ```

   **Field Officer Assignment:**
   ```
   User: field.officer@ministry.gov.rw
   Project: RW-NGRM-2025
   Role: GRM Field Officer
   Administrative Region: Nyarugenge District
   Is Active: ✅ (checked)
   Position Title: Field Officer
   ```

### Step 5.3: Send Activation Codes

For government workers (Department Heads and Field Officers):

1. **Open the assignment record**
2. **Click Actions → Send Activation Email**
3. **Verify email was sent successfully**
4. **Inform users to check their email**

## ✅ Phase 6: System Validation

### Step 6.1: Configuration Checklist

Verify each component is properly configured:

**Administrative Structure:**
- [ ] Administrative Level Types created and linked to project
- [ ] Administrative Regions hierarchy established
- [ ] Regional relationships are correct

**Project Configuration:**
- [ ] Project created and marked as active
- [ ] Project settings configured appropriately
- [ ] All components linked to project

**Classifications:**
- [ ] Departments created with responsible heads
- [ ] Issue statuses cover complete workflow
- [ ] Categories linked to appropriate departments
- [ ] Issue types cover expected scenarios
- [ ] Citizen classifications established

**User Setup:**
- [ ] User accounts created with proper roles
- [ ] Project assignments completed
- [ ] Activation emails sent to government workers
- [ ] Regional assignments cover target areas

### Step 6.2: Test Issue Creation

Create a test issue to verify the complete workflow:

1. **Navigate to GRM Issue → New**

2. **Fill in test data:**
   ```
   Title: Test Water Supply Issue
   Description: This is a test issue to verify system setup
   Status: Open (should auto-populate)
   Project: RW-NGRM-2025
   Category: Water Supply Issues
   Issue Type: Complaint
   Administrative Region: [Select a configured region]
   Citizen: Test Citizen
   Citizen Type: 0=Visible
   Gender: Male
   Contact Medium: facilitator
   Intake Date: [Today]
   Issue Date: [Today]
   ```

3. **Save the issue**

4. **Verify:**
   - [ ] Issue saves successfully
   - [ ] Tracking code is generated
   - [ ] Issue appears in appropriate lists
   - [ ] Assignment workflows function
   - [ ] Status updates work

### Step 6.3: Test User Access

1. **Login as different user types**
2. **Verify appropriate access levels**
3. **Test key functions for each role**
4. **Confirm regional restrictions work**

## 🔧 Common Setup Issues

### Issue: "No Categories Available"
**Solution**: Verify categories are linked to the project via Project Link table

### Issue: "User Cannot See Issues"  
**Solution**: Check user has proper project assignment and role

### Issue: "Activation Email Not Sent"
**Solution**: Verify email settings in System Settings

### Issue: "Regions Not Showing Hierarchy"
**Solution**: Check Parent Region relationships are correct

## 📚 Next Steps

After completing initial setup:

1. **[Project Configuration](./project-configuration.md)** - Advanced project settings
2. **[User Management](./user-management.md)** - Ongoing user administration  
3. **[System Maintenance](./system-maintenance.md)** - Regular maintenance procedures

## 📞 Getting Help

If you encounter issues during setup:
- Review error messages carefully
- Check configuration steps were followed completely
- Verify all required fields are filled
- Contact technical support if needed

---

*Proper initial setup is crucial for system success. Take time to configure everything correctly before going live.*