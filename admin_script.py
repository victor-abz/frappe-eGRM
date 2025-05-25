# Create Administrator user
admin_user = frappe.get_doc(
    {
        "doctype": "User",
        "email": "administrator@example.com",
        "first_name": "Administrator",
        "last_name": "User",
        "full_name": "Administrator User",
        "username": "administrator",
        "enabled": 1,
        "user_type": "System User",
        "send_welcome_email": 0,
    }
)

admin_user.insert(ignore_permissions=True)

# Set password
from frappe.utils.password import update_password

update_password("administrator@example.com", "frappe")

# Add System Manager role
admin_user.add_roles("System Manager")

frappe.db.commit()

print("✅ Administrator user created successfully!")
print("📧 Email: administrator@example.com")
print("🔑 Password: frappe")
print("👤 Username: administrator")
