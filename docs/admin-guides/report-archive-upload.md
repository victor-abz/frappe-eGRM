# Report Archive Upload Instructions

This guide explains how to upload GRM report PDFs to the public reports archive so they are accessible from the public-facing reports page at `/grm-public/reports`.

---

## File Naming Format

All report PDFs must follow a strict naming convention so the archive page can correctly parse and display report metadata.

### Monthly Reports

```
YYYY-MM_ProjectName_Monthly.pdf
```

**Examples:**
- `2025-01_RuralRoadsProject_Monthly.pdf`
- `2025-02_WaterSupplyProject_Monthly.pdf`
- `2025-11_AllProjects_Monthly.pdf`

### Quarterly Reports

```
YYYY-QN_ProjectName_Quarterly.pdf
```

Where `N` is the quarter number (1, 2, 3, or 4).

**Examples:**
- `2025-Q1_RuralRoadsProject_Quarterly.pdf`
- `2025-Q3_WaterSupplyProject_Quarterly.pdf`
- `2025-Q4_AllProjects_Quarterly.pdf`

### Naming Rules

- Use **underscores** (`_`) to separate the date, project name, and report type
- **No spaces** in the filename -- use CamelCase for multi-word project names
- The date portion must come first for correct chronological sorting
- Use `AllProjects` as the project name for aggregate reports

---

## Method 1: Upload via Frappe File Manager

This is the recommended method for non-technical users.

### Steps

1. **Log in** to the Frappe/ERPNext backend as a user with System Manager or GRM Administrator role

2. **Navigate** to the File Manager:
   - Go to **Home > File Manager** (or type "File" in the search bar)

3. **Open the target folder**:
   - Navigate to `Home > grm_reports`
   - If the `grm_reports` folder does not exist, create it:
     - Click **New Folder**
     - Name it `grm_reports`
     - Ensure **Is Private** is **unchecked** (the folder must be public)

4. **Upload the PDF**:
   - Click **Upload**
   - Select the PDF file from your computer
   - Ensure the file follows the naming convention above
   - Click **Upload**

5. **Verify** the file appears in the folder and the URL is accessible (see Verification section below)

---

## Method 2: Upload via SSH (Server Access)

For administrators with server access, files can be placed directly on the filesystem.

### Steps

1. **Connect** to the server via SSH:
   ```bash
   ssh user@your-server
   ```

2. **Navigate** to the public files directory for your site:
   ```bash
   cd /path/to/frappe-bench/sites/your-site.local/public/files/
   ```

3. **Create** the reports directory if it does not exist:
   ```bash
   mkdir -p grm_reports
   ```

4. **Copy** the PDF file into the directory:
   ```bash
   cp /path/to/2025-01_RuralRoadsProject_Monthly.pdf grm_reports/
   ```

5. **Set permissions** so the web server can serve the file:
   ```bash
   chmod 644 grm_reports/*.pdf
   ```

6. **Verify** the file is accessible (see Verification section below)

### Bulk Upload

To upload multiple files at once:

```bash
cp /path/to/reports/*.pdf grm_reports/
chmod 644 grm_reports/*.pdf
```

---

## Verification Steps

After uploading, verify the report is correctly available:

### 1. Check File Accessibility

Open the file URL directly in a browser:

```
https://your-site.example.com/files/grm_reports/2025-01_RuralRoadsProject_Monthly.pdf
```

The PDF should open or download without requiring login.

### 2. Check the Public Archive Page

Navigate to the public reports archive:

```
https://your-site.example.com/grm-public/reports
```

The newly uploaded report should appear in the list with:
- Correct date displayed
- Correct project name
- Correct report type (Monthly/Quarterly)
- A working "Download PDF" link

### 3. Verify from a Non-Authenticated Browser

Open the archive page in a private/incognito browser window (without logging in) to confirm the reports are publicly accessible without authentication.

---

## Directory Structure Reference

On the server filesystem, the reports are stored at:

```
frappe-bench/
  sites/
    your-site.local/
      public/
        files/
          grm_reports/
            2025-01_RuralRoadsProject_Monthly.pdf
            2025-02_RuralRoadsProject_Monthly.pdf
            2025-Q1_RuralRoadsProject_Quarterly.pdf
            ...
```

The public archive page at `/grm-public/reports` automatically scans this directory and lists all PDF files it finds.

---

## Removing Reports from the Archive

To remove a report from the public archive:

- **Via File Manager**: Navigate to the file in `Home > grm_reports`, select it, and delete
- **Via SSH**: Delete the file from the `grm_reports` directory:
  ```bash
  rm grm_reports/2025-01_RuralRoadsProject_Monthly.pdf
  ```

The report will immediately disappear from the public archive page since the page reads the directory contents dynamically.
