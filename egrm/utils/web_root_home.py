"""Serve the citizen portal at ``/`` for every user, staff included.

WHY THIS EXISTS
===============

``role_home_page`` in ``hooks.py`` maps every GRM role to ``app/egrm`` so
staff land on their workspace after logging in. That value is also what
:func:`frappe.website.utils.get_home_page` returns for the bare domain,
and there it is fatal.

:meth:`frappe.website.path_resolver.PathResolver.resolve` evaluates
redirects against the *raw* request path (``""`` for the web root) and
only afterwards substitutes the home page. By then the redirect stage is
over, and ``RedirectPage`` is not among the renderers it goes on to try
(``StaticPage``, ``WebFormPage``, ``DocumentPage``, ``TemplatePage``,
``PrintPage``, ``ListPage``). A desk path matches none of them, so the
root falls through to ``NotFoundPage`` — a logged-in staff member
visiting ``https://<site>/`` got a 404 while ``/grm-portal`` worked.

Pointing ``role_home_page`` at ``desk/egrm`` instead does not help: the
hardcoded desk fast-path at the top of ``resolve()`` tests ``self.path``,
which is still ``""`` for the web root, so it is skipped as well. *Any*
desk path in ``role_home_page`` breaks ``/``.

WHAT THIS DOES
==============

``get_home_page`` short-circuits on ``frappe.local.flags.home_page``
before its per-user cache lookup. Pin that flag to the portal, but only
on requests for the web root. Everything else is untouched — in
particular the ``/api/method/login`` request, where ``get_home_page`` is
what fills ``response["home_page"]``, so ``role_home_page`` still sends
staff to their workspace on login.
"""

from __future__ import annotations

import frappe

PORTAL_ROUTE = "grm-portal"

# The web root, in the spellings Werkzeug can hand us. ``resolve_path``
# treats a blank path as "index" before substituting the home page, so
# both have to count as the root.
_ROOT_PATHS: frozenset[str] = frozenset(("", "index"))


def portal_home_at_web_root() -> None:
	"""``before_request`` hook: force ``/`` to render the portal.

	Never raises — a failure here would take down every page request, and
	the fallback (leave the flag alone) is the framework's own behaviour.
	"""
	try:
		request = getattr(frappe.local, "request", None)
		if request is None:
			return

		path = (getattr(request, "path", "") or "").strip("/ ")
		if path not in _ROOT_PATHS:
			return

		frappe.local.flags.home_page = PORTAL_ROUTE
	except Exception:
		# Deliberately swallowed: see docstring. Logging here would write
		# an error row on every malformed request hitting the root.
		pass
