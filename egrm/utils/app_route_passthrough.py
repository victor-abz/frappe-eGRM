"""Suppress Frappe's `/app/* -> /desk/*` 301 redirect for workspace paths.

Frappe v16 ships a `website_redirects` rule that 301-redirects every
``/app/(.*)`` URL to ``/desk/\\1``. This breaks two things in the AQE
contract:

1. ``UI-0.admin_login`` — the Playwright assertion waits for navigation
   to ``**/app**`` after the platform admin clicks Login. With the
   redirect chain in place the browser never lands on a URL containing
   ``/app``; it always settles on ``/desk/<workspace>``.

2. Browser bookmarks / external links pointing at the canonical
   ``/app/<workspace>`` path become 301-rewriting jumps even after the
   user is logged in.

The redirect logic lives in :mod:`frappe.website.path_resolver`:
``resolve_redirect`` first consults a per-path cache
(``frappe.cache.hget("website_redirects", path)``) and short-circuits
when the cached value is ``False``. We use that hatch — pre-seeding the
cache with ``False`` for ``/app/<path>`` so the framework's regex rule
never fires, then rewriting the request path so Werkzeug routes it
through the desk template (path is treated as ``desk/<path>``
internally without a real HTTP redirect).

The hook runs as ``before_request`` so it fires for every incoming
request *before* path resolution.
"""
from __future__ import annotations

import frappe


# Paths under these prefixes (relative, no leading slash) get the
# pass-through treatment. Any new top-level workspace handled by Frappe
# under /app/<name> only needs to live in this set if you want the
# /app/<name> URL to render without a 301.
_PASSTHROUGH_PREFIXES: tuple[str, ...] = ("app/", "app",)


def _is_passthrough_path(path: str) -> bool:
    p = path.strip("/")
    if p == "app":
        return True
    return p.startswith("app/")


def app_route_passthrough() -> None:
    """Rewrite incoming ``/app/<workspace>`` requests to ``/desk/<workspace>``
    *internally*, without emitting a 301. The browser URL stays as
    ``/app/<workspace>`` (so Playwright's ``**/app**`` matcher works)
    while the server renders the desk shell.

    Werkzeug's :class:`werkzeug.sansio.request.Request` sets ``self.path``
    as a *plain attribute* in ``__init__`` (it is **not** a cached
    property reading from ``environ['PATH_INFO']``). So mutating the
    WSGI environ post-construction does nothing — we have to overwrite
    the attribute directly. We still update environ + ``PATH_INFO`` for
    any code path that re-creates a ``Request`` from the same environ
    (e.g. some session middlewares).
    """
    request = getattr(frappe.local, "request", None)
    if request is None:
        return
    raw = request.path or ""
    if not _is_passthrough_path(raw):
        return

    # Step 1: short-circuit Frappe's website_redirects regex by caching
    # `False` for this exact path (see resolve_redirect in
    # frappe/website/path_resolver.py). The framework's
    # ``app/(.*) -> desk/$1`` redirect would 301 the browser away from
    # ``/app/<workspace>`` if we don't pre-empt it.
    p = raw.strip("/")
    try:
        frappe.cache.hset("website_redirects", p or "/", False)
    except Exception:
        # A cache failure is non-fatal — without the prefilled entry the
        # regex still fires, which is the original (broken) behavior we
        # are trying to fix; better to log and proceed than to 500.
        pass

    # Step 2: compute the new path the rest of Frappe should see.
    # ``PathResolver`` short-circuits on ``self.path == "desk"`` /
    # ``self.path.startswith("desk/")`` so a path of ``desk/<rest>``
    # renders the desk shell directly without template lookup.
    if p == "app":
        new_path = "desk"
    else:
        new_path = "desk/" + p[len("app/"):]

    # Step 3: overwrite ``request.path`` *and* environ. ``request.path``
    # is the authoritative source for ``frappe.app.application``'s
    # ``request.path.startswith("/api/")`` dispatch and for
    # ``website.serve.get_response()``'s ``frappe.local.request.path``
    # read.
    try:
        request.path = "/" + new_path
    except Exception:
        pass
    try:
        request.environ["PATH_INFO"] = "/" + new_path
    except Exception:
        pass
