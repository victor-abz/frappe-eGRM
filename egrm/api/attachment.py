"""
EGRM API - Attachment Management Endpoints
-----------------------------------------
This module contains API endpoints for managing issue attachments.
"""

import frappe
import json
import os
import logging
from frappe import _
from frappe.utils import get_datetime, get_files_path

# Configure logging
log = logging.getLogger(__name__)

@frappe.whitelist()
def upload(issue_id=None, file_data=None, description=None):
    """
    Upload an attachment for an issue
    
    Args:
        issue_id (str): Issue ID
        file_data (FileUpload): Uploaded file data
        description (str, optional): File description
        
    Returns:
        dict: Result of upload
    """
    try:
        user = frappe.session.user
        log.info(f"Uploading attachment for issue {issue_id} by user: {user}")
        
        # Check if issue exists
        if not issue_id or not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}
        
        # Check if user has permission to update the issue
        if not frappe.has_permission("GRM Issue", "write", issue_id):
            log.warning(f"User {user} does not have permission to update issue {issue_id}")
            return {"status": "error", "message": _("You do not have permission to update this issue")}
        
        # Check if file is provided
        if not file_data:
            log.warning(f"No file provided")
            return {"status": "error", "message": _("No file provided")}
        
        # Get issue
        issue = frappe.get_doc("GRM Issue", issue_id)
        
        # Save file
        file_url = save_file(file_data, issue_id)
        if not file_url:
            log.warning(f"Failed to save file")
            return {"status": "error", "message": _("Failed to save file")}
        
        # Add attachment to issue
        issue.append("grm_issue_attachment", {
            "file": file_url,
            "description": description or "",
            "uploaded_by": user,
            "upload_date": get_datetime()
        })
        
        # Save issue
        issue.save()
        
        log.info(f"Successfully uploaded attachment for issue {issue_id}")
        return {
            "status": "success", 
            "message": _("Attachment uploaded successfully"),
            "data": {
                "file_url": file_url
            }
        }
        
    except Exception as e:
        log.error(f"Error in upload_attachment: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def list(issue_id):
    """
    List attachments for an issue
    
    Args:
        issue_id (str): Issue ID
        
    Returns:
        dict: List of attachments
    """
    try:
        user = frappe.session.user
        log.info(f"Listing attachments for issue {issue_id} by user: {user}")
        
        # Check if issue exists
        if not frappe.db.exists("GRM Issue", issue_id):
            log.warning(f"Issue {issue_id} not found")
            return {"status": "error", "message": _("Issue not found")}
        
        # Check if user has permission to read the issue
        if not frappe.has_permission("GRM Issue", "read", issue_id):
            log.warning(f"User {user} does not have permission to read issue {issue_id}")
            return {"status": "error", "message": _("You do not have permission to access this issue")}
        
        # Get attachments
        attachments = frappe.get_all(
            "GRM Issue Attachment",
            filters={"parent": issue_id},
            fields=["name", "file", "description", "uploaded_by", "upload_date"]
        )
        
        # Enhance attachment data
        for attachment in attachments:
            # Get uploaded_by name
            if attachment.uploaded_by:
                user_doc = frappe.get_doc("User", attachment.uploaded_by)
                attachment.uploaded_by_name = user_doc.full_name
            
            # Get file metadata
            file_url = attachment.file
            attachment.filename = os.path.basename(file_url) if file_url else ""
            
            # Determine file type
            if attachment.filename:
                attachment.file_type = get_file_type(attachment.filename)
            else:
                attachment.file_type = "unknown"
        
        log.info(f"Returning {len(attachments)} attachments for issue {issue_id}")
        return {"status": "success", "data": attachments}
        
    except Exception as e:
        log.error(f"Error in list_attachments: {str(e)}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def download(attachment_id):
    """
    Download an attachment
    
    Args:
        attachment_id (str): Attachment ID
        
    Returns:
        dict: URL to download the attachment
    """
    try:
        user = frappe.session.user
        log.info(f"Downloading attachment {attachment_id} by user: {user}")
        
        # Find attachment
        attachments = frappe.get_all(
            "GRM Issue Attachment",
            filters={"name": attachment_id},
            fields=["parent", "file"]
        )
        
        if not attachments:
            log.warning(f"Attachment {attachment_id} not found")
            return {"status": "error", "message": _("Attachment not found")}
        
        attachment = attachments[0]
        
        # Check if user has permission to read the issue
        if not frappe.has_permission("GRM Issue", "read", attachment.parent):
            log.warning(f"User {user} does not have permission to read issue {attachment.parent}")
            return {"status": "error", "message": _("You do not have permission to access this attachment")}
        
        # Get file URL
        file_url = attachment.file
        if not file_url:
            log.warning(f"File URL not found for attachment {attachment_id}")
            return {"status": "error", "message": _("File not found")}
        
        # Return download URL
        log.info(f"Returning download URL for attachment {attachment_id}")
        return {
            "status": "success", 
            "data": {
                "download_url": file_url
            }
        }
        
    except Exception as e:
        log.error(f"Error in download_attachment: {str(e)}")
        return {"status": "error", "message": str(e)}

# Utility functions

def save_file(file_data, issue_id):
    """
    Save an uploaded file
    
    Args:
        file_data (FileUpload): Uploaded file data
        issue_id (str): Issue ID
        
    Returns:
        str: File URL
    """
    try:
        # Get filename
        filename = file_data.filename
        
        # Create folder for issue if it doesn't exist
        folder_path = os.path.join(get_files_path(), "grm_issues", issue_id)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
        
        # Generate unique filename
        timestamp = get_datetime().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{timestamp}_{filename}"
        
        # Save file
        file_path = os.path.join(folder_path, unique_filename)
        with open(file_path, "wb+") as f:
            f.write(file_data.get_content())
        
        # Return file URL (relative to site path)
        return f"/files/grm_issues/{issue_id}/{unique_filename}"
        
    except Exception as e:
        log.error(f"Error saving file: {str(e)}")
        return None

def get_file_type(filename):
    """
    Get file type based on extension
    
    Args:
        filename (str): Filename
        
    Returns:
        str: File type
    """
    extension = os.path.splitext(filename)[1].lower()
    
    image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg"]
    document_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf"]
    audio_extensions = [".mp3", ".wav", ".ogg", ".aac", ".flac"]
    video_extensions = [".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv"]
    
    if extension in image_extensions:
        return "image"
    elif extension in document_extensions:
        return "document"
    elif extension in audio_extensions:
        return "audio"
    elif extension in video_extensions:
        return "video"
    else:
        return "other"
