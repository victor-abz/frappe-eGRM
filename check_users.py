import frappe

frappe.init(site="egrm.local")
frappe.connect()

users = frappe.get_all(
    "User",
    filters={"email": ["like", "%@test.gov.rw"]},
    fields=["email", "first_name", "last_name", "full_name"],
    limit=5,
)

print("Checking full_name field for newly created users:")
print("=" * 60)

for user in users:
    print(f"Email: {user.email}")
    print(f"First Name: {user.first_name}")
    print(f"Last Name: {user.last_name}")
    print(f"Full Name: {user.full_name}")
    print("-" * 40)

frappe.destroy()
