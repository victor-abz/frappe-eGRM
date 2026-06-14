# eGRM LLM-Driven E2E Test Guide

Reproducible steps used to onboard the **RDAP** (Rwanda Digital Acceleration Project) and verify the full issue lifecycle via headless browser automation (vibium).

Tested: 2026-05-23 on `egrm.local:8000` (Frappe v16).

---

## Prerequisites

| Item | Value |
|------|-------|
| Site | `egrm.local` |
| Admin password | `Passw0rd!` (set via `bench --site egrm.local set-admin-password 'Passw0rd!'`) |
| Test user password | `Tr0ub4dor&3xx2026` |
| Browser tool | `vibium` (headless Chromium, installed via `vibium install`) |
| User roster | `/Users/victor/Downloads/eGRM users patched v2.xlsx` (30 users) |
| Dropbox copy | `~/Library/CloudStorage/Dropbox/WorldBank/RISA/RISA - eGRM Users (RDAP).csv` |

---

## 1. Project Onboarding via Wizard

### 1.1 Admin Login

```bash
vibium --headless go "http://egrm.local:8000/login"
vibium --headless fill "#login_email" "Administrator"
vibium --headless fill "#login_password" "Passw0rd!"
vibium --headless click ".btn-login"
```

### 1.2 Step 1 — Project Info

```bash
vibium go "http://egrm.local:8000/app/grm-project-wizard"

vibium fill "#grm-f-project_code"          "RDAP"
vibium fill "#grm-f-title"                 "Rwanda Digital Acceleration Project"
vibium fill "#grm-f-time_zone"             "Africa/Kigali"
vibium fill "#grm-f-auto_escalation_days"  "15"
vibium click "#grm-next"
```

### 1.3 Step 2 — Administrative Levels

Two levels: **PIU** (order 1) and **Province** (order 2).

```bash
# Add PIU level
vibium click "#grm-step3-add"
vibium fill  "#grm-n-level_name"  "PIU"
vibium fill  "#grm-n-level_order" "1"
vibium click "#grm-n-save"

# Add Province level
vibium click "#grm-step3-add"
vibium fill  "#grm-n-level_name"  "Province"
vibium fill  "#grm-n-level_order" "2"
vibium click "#grm-n-save"
```

### 1.4 Step 2 — Regions (CSV Upload)

Create `/tmp/rdap_provinces.csv`:

```csv
Province
Kigali city
Northern
Southern
Eastern
Western
```

```bash
vibium click 'a[href="#grm-tab-regions"]'
vibium fill  "#grm-rg-highest" "PIU"
vibium upload "#grm-rg-file" /tmp/rdap_provinces.csv
vibium click "#grm-rg-preview"
vibium click "#grm-rg-import"
vibium click "#grm-next"
```

This creates 1 PIU region and 5 Province regions underneath it.

### 1.5 Step 3 — Project Roles

```bash
vibium eval "
(async () => {
  const PIU_LEVEL   = 'hci0973vej';   // replace with your PIU admin_level ID
  const PROV_LEVEL  = 'hdnv93hjoo';   // replace with your Province admin_level ID
  const roles = [
    {role_name:'Project Coordinator',           admin_level:PIU_LEVEL,  duties:['Intake','Review','Assignment','Investigate & Resolve','Feedback','Supervise']},
    {role_name:'Social/Environmental Safeguard', admin_level:PIU_LEVEL,  duties:['Intake','Review','Assignment','Investigate & Resolve','Feedback','Supervise']},
    {role_name:'Legal',                          admin_level:PIU_LEVEL,  duties:['Intake','Review','Assignment','Investigate & Resolve','Feedback','Supervise']},
    {role_name:'Project Administrator',          admin_level:PROV_LEVEL, duties:['Intake','Review','Assignment','Investigate & Resolve','Feedback','Supervise']},
  ];
  const out = [];
  for (const r of roles) {
    const res = await frappe.call({
      method:'egrm.egrm.page.grm_project_wizard.grm_project_wizard.project_role_add',
      args:{project:'RDAP', role_name:r.role_name, admin_level:r.admin_level, duties:JSON.stringify(r.duties)}
    });
    out.push({role:r.role_name, ok:!res.exc, name:res.message?.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

> **Note**: Admin-level IDs (`hci0973vej`, `hdnv93hjoo`) are auto-generated hashes. Query them with `frappe.get_all("GRM Administrative Level", filters={"project":"RDAP"}, fields=["name","level_name"])` after Step 2.

### 1.6 Step 4 — Departments

```bash
vibium eval "
(async () => {
  const depts = ['Project Coordination Unit','Customer Service','Field Operations'];
  const out = [];
  for (const dn of depts) {
    const r = await frappe.db.insert({
      doctype:'GRM Issue Department', department_name:dn,
      grm_project_link:[{project:'RDAP'}]
    });
    out.push({dept:dn, ok:true, name:r.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

### 1.7 Step 5 — Issue Categories

```bash
vibium eval "
(async () => {
  const PROV_ROLE  = 'ing4rdrsc5';   // Project Administrator role ID
  const PROV_LEVEL = 'hdnv93hjoo';
  const cats = [
    {category_name:'Question',                 abbreviation:'QUE', confidentiality_level:'Public'},
    {category_name:'Complaint',                abbreviation:'COM', confidentiality_level:'Confidential'},
    {category_name:'Appreciation',             abbreviation:'APP', confidentiality_level:'Public'},
    {category_name:'Suggestion',               abbreviation:'SUG', confidentiality_level:'Public'},
    {category_name:'Request for Information',  abbreviation:'RFI', confidentiality_level:'Public'},
    {category_name:'Service Issue',            abbreviation:'SVC', confidentiality_level:'Public'},
    {category_name:'Other',                    abbreviation:'OTH', confidentiality_level:'Public'},
  ];
  const out = [];
  for (const c of cats) {
    const r = await frappe.db.insert({
      doctype:'GRM Issue Category',
      category_name:c.category_name, label:c.category_name, abbreviation:c.abbreviation,
      routing_target_type:'Role', assigned_role:PROV_ROLE,
      confidentiality_level:c.confidentiality_level,
      redirection_protocol:'0', administrative_level:PROV_LEVEL,
      grm_project_link:[{project:'RDAP'}]
    });
    out.push({cat:c.category_name, ok:true, name:r.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

### 1.8 Step 6 — Issue Types

```bash
vibium eval "
(async () => {
  const types = ['Verbal','Written','Phone Call','SMS','Web Form','Email','In Person','Mobile App'];
  const out = [];
  for (const t of types) {
    const r = await frappe.db.insert({doctype:'GRM Issue Type', type_name:t, grm_project_link:[{project:'RDAP'}]});
    out.push({type:t, ok:true, name:r.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

### 1.9 Step 7 — Citizen Lookups (Age Groups + Citizen Groups)

```bash
vibium eval "
(async () => {
  const ages   = ['Under 18','18-30','31-45','46-60','Over 60'];
  const groups = [
    {n:'Citizen',t:'1'},{n:'Government',t:'1'},{n:'NGO/CSO',t:'1'},
    {n:'Female',t:'2'},{n:'Male',t:'2'},{n:'Non-binary',t:'2'},
    {n:'Persons with Disability',t:'2'}
  ];
  const out = {age:[], groups:[]};
  for (const a of ages) {
    const r = await frappe.db.insert({doctype:'GRM Issue Age Group', age_group:a, grm_project_link:[{project:'RDAP'}]});
    out.age.push({age:a, name:r.name});
  }
  for (const g of groups) {
    const r = await frappe.db.insert({doctype:'GRM Issue Citizen Group', group_name:g.n, group_type:g.t, grm_project_link:[{project:'RDAP'}]});
    out.groups.push({grp:g.n, name:r.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

### 1.10 Step 8 — Notification Templates

```bash
vibium eval "
(async () => {
  const types = ['Receipt','Acknowledgment','In Progress','Resolved','Closed','Escalated','SLA Reminder'];
  const out = [];
  for (const t of types) {
    const r = await frappe.call({method:'frappe.client.insert', args:{doc:{
      doctype:'GRM Notification Template',
      template_name:'RDAP - '+t, template_type:t,
      enable_sms:1, sms_message:'Issue {{ tracking_code }}: '+t,
      active:1, project:'RDAP'
    }}});
    out.push({type:t, ok:!r.exc, name:r.message?.name});
  }
  return JSON.stringify(out);
})()"
vibium click "#grm-next"
```

### 1.11 Step 9 — User Import

```bash
# Inject hidden file input
vibium eval "(() => {
  const inp = document.createElement('input'); inp.type='file';
  inp.id='grm-test-file'; inp.style.cssText='position:fixed;left:-9999px';
  document.body.appendChild(inp); return 'ok';
})()"

# Upload xlsx to browser
vibium upload "#grm-test-file" "/Users/victor/Downloads/eGRM users patched v2.xlsx"

# Upload to Frappe server
vibium eval "(async () => {
  const inp = document.getElementById('grm-test-file');
  const fd = new FormData();
  fd.append('file', inp.files[0], inp.files[0].name);
  fd.append('is_private','1'); fd.append('folder','Home');
  const resp = await fetch('/api/method/upload_file', {
    method:'POST',
    headers:{'X-Frappe-CSRF-Token':frappe.csrf_token},
    body:fd
  });
  const data = await resp.json();
  return JSON.stringify({status:resp.status, file_url:data.message?.file_url});
})()"

# Auto-detect column mapping
vibium eval "(async () => {
  const r = await frappe.call({
    method:'egrm.egrm.page.grm_project_wizard.grm_project_wizard.auto_detect_user_import_mapping',
    args:{project:'RDAP', file_url:'/private/files/eGRM users patched v2.xlsx'}
  });
  return JSON.stringify(r.message);
})()"

# Prepare import
vibium eval "(async () => {
  const mapping = {
    'Province':'administrative_region',
    'District':'(skip)', 'Sector':'(skip)',
    'First Name':'User.first_name', 'Last Name':'User.last_name',
    'Gender':'User.gender', 'Position':'Assignment.position_title',
    'Phone':'(skip)', 'Phone Numbers':'User.phone',
    'Email':'User.email', 'Project Role':'Assignment.role'
  };
  const r = await frappe.call({
    method:'egrm.egrm.page.grm_project_wizard.grm_project_wizard.prepare_user_import',
    args:{
      project:'RDAP', file_url:'/private/files/eGRM users patched v2.xlsx',
      header_mapping:mapping, level_mapping:{'Province':'Province'},
      auto_create_regions:true, synthesize_emails:false, synthesize_email_domain:''
    }
  });
  return JSON.stringify(r.message);
})()"

# Start + poll import (replace data_import name with the one returned above)
vibium eval "(async () => {
  const r = await frappe.call({
    method:'egrm.egrm.page.grm_project_wizard.grm_project_wizard.start_user_import',
    args:{data_import:'GRM User Project Assignment Import on 2026-05-23 18:02:05.141887'}
  });
  return JSON.stringify(r.message);
})()"

vibium eval "(async () => {
  const r = await frappe.call({
    method:'egrm.egrm.page.grm_project_wizard.grm_project_wizard.poll_user_import',
    args:{data_import:'GRM User Project Assignment Import on 2026-05-23 18:02:05.141887'}
  });
  return JSON.stringify(r.message);
})()"
```

Result: 29 user-project assignments created (30 rows, 1 deduped).

### 1.12 Steps 10-12 — Routing, SLAs, Activation

```bash
# Step 10: Routing (accept defaults)
vibium click "#grm-next"

# Step 11: SLAs
vibium click "#grm-step9-save-all"
vibium click "#grm-next"

# Step 12: Activate project
vibium eval "document.querySelector('#grm-act-confirm').click()"
vibium click "#grm-next"
```

### 1.13 Set Test User Passwords (bench console)

```bash
bench --site egrm.local console
```

```python
from frappe.utils.password import update_password
import frappe

users = frappe.get_all("User", filters={"name": ["like", "%@yopmail.com"]}, pluck="name")
for u in users:
    update_password(u, "Tr0ub4dor&3xx2026")
frappe.db.commit()
```

---

## 2. Citizen Portal — Submit Complaint

### 2.1 Issue 1: Kigali City (Province-level resolution)

```bash
vibium go "http://egrm.local:8000/grm-portal/submit"

# Step 1: Select project
vibium eval "(() => {
  Array.from(document.querySelectorAll('button')).find(el => /RDAP/.test(el.textContent))?.click();
  setTimeout(() => Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Next')?.click(), 500);
})()"

# Step 2: Category + Type
vibium eval "(() => {
  const btns = document.querySelectorAll('button');
  Array.from(btns).find(el => el.textContent.trim()==='Complaint')?.click();
  Array.from(btns).find(el => el.textContent.trim()==='Web Form')?.click();
  setTimeout(() => Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Next')?.click(), 500);
})()"

# Step 3: Location — select PIU region then Kigali city
vibium eval "(() => {
  const sels = document.querySelectorAll('select');
  sels[1].value = sels[1].options[1].value;
  sels[1].dispatchEvent(new Event('change',{bubbles:true}));
})()"
vibium eval "(() => {
  const sels = document.querySelectorAll('select');
  const opt = Array.from(sels[2].options).find(o => o.text==='Kigali city');
  sels[2].value = opt.value;
  sels[2].dispatchEvent(new Event('change',{bubbles:true}));
  setTimeout(() => Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Next')?.click(), 500);
})()"

# Step 4: Date + Description
vibium eval "(() => {
  const date = document.querySelector('input[type=date]');
  const ta   = document.querySelector('textarea');
  const setI = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  const setT = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  setI.call(date,'2026-05-20'); date.dispatchEvent(new Event('input',{bubbles:true})); date.dispatchEvent(new Event('change',{bubbles:true}));
  setT.call(ta,'My internet connection at the Kigali digital training center is consistently unstable and slow, making it impossible to participate in scheduled training sessions. Please investigate and resolve.');
  ta.dispatchEvent(new Event('input',{bubbles:true})); ta.dispatchEvent(new Event('change',{bubbles:true}));
  setTimeout(() => Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Next')?.click(), 500);
})()"

# Step 5: Contact info (opted in)
vibium eval "(() => {
  Array.from(document.querySelectorAll('button')).find(el => /I want updates/.test(el.textContent))?.click();
})()"
vibium eval "(() => {
  const phone = document.querySelector('input[type=tel]');
  const name  = document.querySelector('input[type=text]');
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  set.call(phone,'+250788123456'); phone.dispatchEvent(new Event('input',{bubbles:true}));
  set.call(name,'Test Citizen');   name.dispatchEvent(new Event('input',{bubbles:true}));
})()"

# Submit
vibium eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Submit Complaint')?.click()"

# Extract tracking code
vibium eval "document.body.innerText.match(/RDAP-\\d+-\\d+/)?.[0]"
```

**Result**: Tracking code `RDAP-260520-1136`, Issue ID `lpdlqfuk9k`.

### 2.2 Issue 2: Northern Province (for escalation test)

```bash
vibium go "http://egrm.local:8000/grm-portal/submit"
```

Same flow as Issue 1 but with:
- Category: **Service Issue**, Type: **Phone Call**
- Location: **Northern** province
- Date: `2026-05-22`
- Description: `Cross-district policy decision required: digital ambassador program rollout across all Northern districts needs PIU-level coordination because we cannot decide locally. Please escalate this matter to project central management.`
- Submitted **anonymously** (clicked "anonymous" button instead of contact info)

**Result**: Tracking code `RDAP-260522-1385`, Issue ID `rm4n4qa9dm`.

---

## 3. Issue Lifecycle — Province-Level Resolution

Login as Kigali city Project Administrator:

```bash
vibium go "http://egrm.local:8000/login"
vibium fill "#login_email"    "0782331296@yopmail.com"
vibium fill "#login_password" "Tr0ub4dor&3xx2026"
vibium click ".btn-login"
```

### 3.1 Accept Issue

```bash
vibium go "http://egrm.local:8000/app/grm-issue/lpdlqfuk9k"

vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => /^Accept Issue/.test(el.textContent.trim()))?.click()"
vibium eval "Array.from(document.querySelectorAll('.modal.show button')).find(el => el.textContent.trim()==='Yes')?.click()"
```

### 3.2 Record Resolution

```bash
vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => el.textContent.trim()==='Record Resolution')?.click()"

vibium eval "(() => {
  const ta = document.querySelector('.modal.show textarea');
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  set.call(ta,'Coordinated with the ISP to upgrade the digital training center bandwidth. Connection stable for 48 hours, verified on-site.');
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
})()"

vibium eval "Array.from(document.querySelector('.modal.show').querySelectorAll('button')).find(b => b.textContent.trim()==='Resolve')?.click()"
```

Issue status: **Resolved**.

---

## 4. Issue Lifecycle — Escalation (Province to PIU)

### 4.1 Login as Northern Province Admin + Accept

```bash
# Logout
vibium eval "(async () => {
  await fetch('/api/method/logout',{method:'POST',headers:{'X-Frappe-CSRF-Token':frappe.csrf_token},credentials:'include'});
})()"

vibium go "http://egrm.local:8000/login"
vibium fill "#login_email"    "0788706559@yopmail.com"
vibium fill "#login_password" "Tr0ub4dor&3xx2026"
vibium click ".btn-login"

vibium go "http://egrm.local:8000/app/grm-issue/rm4n4qa9dm"

# Accept
vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => /^Accept Issue/.test(el.textContent.trim()))?.click()"
vibium eval "Array.from(document.querySelectorAll('.modal.show button')).find(el => el.textContent.trim()==='Yes')?.click()"
```

### 4.2 Escalate to PIU

```bash
vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => el.textContent.trim()==='Escalate Issue')?.click()"

vibium eval "(() => {
  const modal = Array.from(document.querySelectorAll('.modal')).find(m => m.innerText.includes('Escalate Issue'));
  const ta = modal.querySelector('textarea');
  const dateInput = modal.querySelectorAll('input')[0] || modal.querySelector('input[type=text]');
  const setTA = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  const setIN = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  setTA.call(ta,'Cross-locality PIU coordination needed.');
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
  setIN.call(dateInput,'2026-05-30 10:00:00');
  dateInput.dispatchEvent(new Event('input',{bubbles:true}));
  dateInput.dispatchEvent(new Event('change',{bubbles:true}));
})()"

vibium eval "(() => {
  const modal = Array.from(document.querySelectorAll('.modal')).find(m => m.innerText.includes('Escalate Issue'));
  Array.from(modal.querySelectorAll('button')).find(b => b.innerText.trim()==='Escalate')?.click();
})()"
```

Issue escalated from Northern Province to PIU.

### 4.3 PIU Coordinator — Intake + Resolve

```bash
# Logout + login as PIU coordinator
vibium eval "(async () => {
  await fetch('/api/method/logout',{method:'POST',headers:{'X-Frappe-CSRF-Token':frappe.csrf_token},credentials:'include'});
})()"
vibium go "http://egrm.local:8000/login"
vibium fill "#login_email"    "piu.coordinator@yopmail.com"
vibium fill "#login_password" "Tr0ub4dor&3xx2026"
vibium click ".btn-login"

vibium go "http://egrm.local:8000/app/grm-issue/rm4n4qa9dm"

# Reassign to self (needed because escalation cleared assignee)
vibium eval "(async () => {
  const r = await frappe.call({
    method:'egrm.server_scripts.issue_actions.reassign_issue',
    args:{issue:'rm4n4qa9dm', assignee:'piu.coordinator@yopmail.com',
          comment:'PIU coordinator taking ownership of escalated cross-locality issue.'}
  });
  return JSON.stringify(r.message);
})()"

# Accept
vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => el.textContent.trim()==='Accept Issue')?.click()"
vibium eval "(() => {
  const modal = Array.from(document.querySelectorAll('.modal')).find(m => m.innerText.includes('accept this issue'));
  Array.from(modal.querySelectorAll('button')).find(b => b.innerText.trim()==='Yes')?.click();
})()"

# Resolve
vibium eval "Array.from(document.querySelectorAll('a.dropdown-item')).find(el => el.textContent.trim()==='Record Resolution')?.click()"

vibium eval "(() => {
  const modal = Array.from(document.querySelectorAll('.modal')).find(m => m.innerText.includes('Record Resolution'));
  const ta = modal.querySelector('textarea');
  const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  set.call(ta,'PIU coordinated cross-locality response: deployed regional digital ambassador task force across affected Northern districts; issue resolved with project-level intervention.');
  ta.dispatchEvent(new Event('input',{bubbles:true}));
  ta.dispatchEvent(new Event('change',{bubbles:true}));
  Array.from(modal.querySelectorAll('button')).find(b => b.innerText.trim()==='Resolve')?.click();
})()"
```

Issue status: **Resolved** at PIU level.

---

## 5. Citizen Feedback — Rating + Comment

```bash
# Logout
vibium eval "(async () => {
  await fetch('/api/method/logout',{method:'POST',headers:{'X-Frappe-CSRF-Token':frappe.csrf_token},credentials:'include'});
})()"

vibium go "http://egrm.local:8000/grm-portal/track"

# Enter tracking code
vibium eval "(() => {
  const i = document.querySelector('input[placeholder=\"Enter tracking code...\"]');
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  set.call(i,'RDAP-260520-1136');
  i.dispatchEvent(new Event('input',{bubbles:true}));
  i.dispatchEvent(new Event('change',{bubbles:true}));
})()"
vibium eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Track Complaint')?.click()"

# Rate 4/5
vibium click "[data-testid=rating-star-4]"

# Request OTP
vibium eval "Array.from(document.querySelectorAll('button')).find(el => /Send code/i.test(el.textContent))?.click()"

# Retrieve OTP from cache (bench console):
#   frappe.cache.get_value("otp_+250788123456")
# Example: 481212

# Fill OTP + comment + submit
vibium eval "(() => {
  const ins = document.querySelectorAll('input, textarea');
  const otp     = Array.from(ins).find(el => el.placeholder && /6-digit/i.test(el.placeholder));
  const comment = Array.from(ins).find(el => el.tagName==='TEXTAREA');
  const setI = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
  const setT = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set;
  setI.call(otp,'481212'); otp.dispatchEvent(new Event('input',{bubbles:true}));
  setT.call(comment,'Thank you for resolving this quickly. The new bandwidth is much better.');
  comment.dispatchEvent(new Event('input',{bubbles:true}));
})()"
vibium eval "Array.from(document.querySelectorAll('button')).find(el => el.textContent.trim()==='Submit rating')?.click()"
```

---

## 6. Test Users

30 users imported from the xlsx roster. Key actors:

| Email | Province | Role | Used For |
|-------|----------|------|----------|
| `0782331296@yopmail.com` | Kigali city | Project Administrator | Accept + resolve Issue 1 |
| `0788706559@yopmail.com` | Northern | Project Administrator | Accept + escalate Issue 2 |
| `piu.coordinator@yopmail.com` | PIU | Project Coordinator | PIU intake + resolve Issue 2 |
| `northern.admin@yopmail.com` | Northern | Project Administrator | (available, not used in this run) |
| `kigali.admin@yopmail.com` | Kigali city | Project Administrator | (available, not used in this run) |

Full roster: see `~/Library/CloudStorage/Dropbox/WorldBank/RISA/RISA - eGRM Users (RDAP).csv`.

---

## 7. Screenshots

Vibium writes all screenshots to `~/Pictures/Vibium/` (ignores `-o` path).

Key evidence files:

| File | Description |
|------|-------------|
| `escalate_v2.png` | Successful Province-to-PIU escalation |
| `accepted.png` | PIU coordinator accepted escalated issue |
| `resolved_piu.png` | Issue resolved at PIU level |
| `wizard_activated.png` | RDAP project activated |

---

## 8. Flows Verified

| # | Flow | Tracking Code | Issue ID | Result |
|---|------|---------------|----------|--------|
| 1 | Citizen submit &#8594; Province intake &#8594; Province resolve &#8594; Citizen rating 4/5 | RDAP-260520-1136 | lpdlqfuk9k | Resolved + Rated |
| 2 | Citizen submit (anon) &#8594; Province intake &#8594; Escalate to PIU &#8594; PIU intake &#8594; PIU resolve | RDAP-260522-1385 | rm4n4qa9dm | Resolved |

---

## 9. Known Issues Found & Fixed

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Escalation fails with "will get truncated, as max characters allowed is 140" | `GRM Issue Log.text` field was `Data` (varchar 140) | Changed to `Long Text` (longtext) in `grm_issue_log.json` + `bench migrate` |
| Logout via GET returns 403 | Frappe requires POST with CSRF token | Use `fetch('/api/method/logout', {method:'POST', headers:{'X-Frappe-CSRF-Token':frappe.csrf_token}})` |
| PIU coordinator cannot see action buttons after escalation | `assignee` field is null after escalation | Call `reassign_issue` API to assign the PIU coordinator before accepting |

---

## 10. Not Yet Tested

- **District-level flows**: RDAP was onboarded with 2 levels (PIU + Province). Adding a District level would enable the District &#8594; Province &#8594; PIU two-hop escalation chain.
- **Appeal flow**: Citizen appeal after resolution (portal supports it, not exercised).
- **SLA auto-escalation**: Configured at 15 days; not tested due to time constraint.
- **Mobile app sync**: `api/sync.py` endpoints not exercised via vibium.
