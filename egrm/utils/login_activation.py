"""Activate a worker's assignments the first time they sign in.

The activation OTP exists to prove that the person holding the account is
who the project meant to invite. A successful login proves the same thing
— they hold the credentials. Requiring both left imported workers
stranded: their assignment rows stayed ``Pending Activation``, and every
project-scoped query (mobile sync, region lookup, issue filtering)
requires ``Activated``. The result was a worker who signed in fine and
then saw an empty app.

Registered as ``on_session_creation`` in hooks.py, so it covers the desk,
the portal and the mobile app's ``/api/method/login`` in one place.
"""

from __future__ import annotations

import frappe
from frappe.utils import now

# States that represent an unfinished signup, and so are superseded by a
# successful login. `Suspended` is deliberately absent: that is an admin
# block, not an unfinished signup, and must survive a login.
RESUMABLE_STATES = ("Pending Activation", "Draft", "Expired")

SKIP_USERS = ("Guest", "Administrator")


def activate_pending_assignments_on_login(login_manager=None) -> list[str]:
	"""Mark the current user's unfinished assignments as activated.

	Returns the names of the assignments that changed, so the caller (and
	the tests) can tell a first login from a subsequent one.

	Never raises: this runs inside session creation, and a failure here
	must not cost the user their sign-in.
	"""
	try:
		user = frappe.session.user
		if not user or user in SKIP_USERS:
			return []

		names = frappe.get_all(
			"GRM User Project Assignment",
			filters={
				"user": user,
				"is_active": 1,
				"activation_status": ["in", RESUMABLE_STATES],
			},
			pluck="name",
		)
		if not names:
			return []

		activated: list[str] = []
		# `validate_creator_permissions` rejects a worker editing their own
		# assignment — correctly, since that guard is about who may hand out
		# assignments. This is not the worker acting, it is the system
		# finishing their signup, so write as the system rather than punch a
		# hole in the guard.
		try:
			frappe.set_user("Administrator")
			for name in names:
				try:
					doc = frappe.get_doc("GRM User Project Assignment", name)
					doc.activation_status = "Activated"
					doc.activated_on = now()
					doc.activation_attempts = 0
					# The code has served its purpose; leaving it outstanding
					# would let a stale OTP be redeemed later.
					doc.activation_code = None
					doc.activation_expires_on = None
					doc.flags.ignore_permissions = True
					doc.save(ignore_permissions=True)
					activated.append(name)
				except Exception as e:
					# One bad row must not strand the others, nor the login.
					frappe.log_error(f"Error activating {name} on login: {e!s}")
		finally:
			frappe.set_user(user)

		if activated:
			frappe.db.commit()
			frappe.log(f"Activated {len(activated)} assignment(s) for {user} on login")
		return activated

	except Exception as e:
		frappe.log_error(f"Error in activate_pending_assignments_on_login: {e!s}")
		return []
