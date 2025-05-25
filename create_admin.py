#!/usr/bin/env python3

import frappe


def create_admin_user():
    """Create Administrator user with default password"""
    try:
        frappe.init(site="egrm.local")
        frappe.connect()

        # Check if Administrator already exists
        existing_admin = frappe.db.exists("User", "administrator@example.com")
        if existing_admin:
            print("Administrator user already exists")
            return

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

    except Exception as e:
        print(f"❌ Error creating Administrator: {str(e)}")
        frappe.db.rollback()
    finally:
        frappe.destroy()


if __name__ == "__main__":
    create_admin_user()
