"""Tests for ``egrm.utils.web_root_home``.

Regression cover for the bare-domain 404: ``role_home_page`` points staff
at ``app/egrm``, which :class:`frappe.website.path_resolver.PathResolver`
cannot render for ``/`` because redirects are evaluated before the
home-page substitution. See the module docstring on the fix for the full
chain.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.path_resolver import PathResolver
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

from egrm.utils.web_root_home import PORTAL_ROUTE, portal_home_at_web_root


def _request(path: str) -> Request:
    """A real Werkzeug request — PathResolver reads ``request.environ``."""
    return Request(
        EnvironBuilder(path=path, base_url="http://egrm.local").get_environ()
    )


class TestWebRootHome(FrappeTestCase):
    def setUp(self) -> None:
        self._prev_request = getattr(frappe.local, "request", None)
        self._prev_flag = frappe.local.flags.home_page
        self._prev_user = frappe.session.user

    def tearDown(self) -> None:
        frappe.local.request = self._prev_request
        frappe.local.flags.home_page = self._prev_flag
        frappe.set_user(self._prev_user)

    def test_flag_pinned_for_web_root(self) -> None:
        for path in ("/", "/index"):
            with self.subTest(path=path):
                frappe.local.request = _request(path)
                frappe.local.flags.home_page = None

                portal_home_at_web_root()

                self.assertEqual(frappe.local.flags.home_page, PORTAL_ROUTE)

    def test_flag_untouched_off_the_web_root(self) -> None:
        """Login in particular must keep resolving via ``role_home_page`` so
        staff still land on their workspace after signing in."""
        paths = (
            "/api/method/login",
            "/grm-portal",
            "/grm-portal/submit",
            "/app/egrm",
        )
        for path in paths:
            with self.subTest(path=path):
                frappe.local.request = _request(path)
                frappe.local.flags.home_page = None

                portal_home_at_web_root()

                self.assertIsNone(frappe.local.flags.home_page)

    def test_web_root_renders_portal_for_staff(self) -> None:
        """The actual regression: a logged-in staff user hitting ``/`` used
        to fall through to ``NotFoundPage``."""
        frappe.local.request = _request("/")
        frappe.local.flags.home_page = None
        frappe.set_user("Administrator")
        frappe.cache.hdel("home_page", "Administrator")

        # ``get_home_page`` ignores ``flags.home_page`` while
        # ``frappe.in_test`` is set, which would mask the very behaviour
        # under test. Drop it for the resolve and put it back.
        was_in_test = frappe.in_test
        frappe.in_test = False
        try:
            portal_home_at_web_root()
            endpoint, renderer = PathResolver("").resolve()
        finally:
            frappe.in_test = was_in_test

        self.assertEqual(endpoint, PORTAL_ROUTE)
        self.assertNotEqual(type(renderer).__name__, "NotFoundPage")

    def test_hook_never_raises(self) -> None:
        """A failure here would break every request, so the hook swallows."""
        frappe.local.request = None
        frappe.local.flags.home_page = None

        portal_home_at_web_root()  # must not raise

        self.assertIsNone(frappe.local.flags.home_page)
