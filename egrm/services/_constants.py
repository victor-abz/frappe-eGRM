"""Shared constants for the duty-driven services layer.

Review fix B5: single source of truth for the
``activation_status`` values that count as "actively dispatchable".

Both ``assignee_routing`` and ``duty_coverage`` filter on this column
when picking candidate assignees. Previously the two modules disagreed
on whether ``Pending Activation`` rows should be considered, which led
to a real-world bug: ``duty_coverage`` reports a region as covered, but
``assignee_routing`` immediately filters that same coverage row out at
dispatch time.

We standardize on the **inclusive** set (Activated + Pending Activation
+ "" sentinel for legacy rows) because that matches what an operator
expects from "covered" — even a row that hasn't completed the email-OTP
activation handshake holds the duty and is meant to receive issues.
"""

# Used by both:
#   - egrm.services.assignee_routing.ACTIVE_STATUSES (re-export)
#   - egrm.services.duty_coverage.compute_coverage (SQL IN clause)
ACTIVE_ASSIGNMENT_STATUSES: tuple[str, ...] = (
	"Activated",
	"Pending Activation",
	"",
)
