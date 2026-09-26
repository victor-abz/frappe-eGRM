"""Serve the pre-built eGRM user guide from `/guide`.

The guide is a static export (fumadocs/Next.js) that is built into
`egrm/public/guide/` and ships with the app, so it is always in step with the
code that is deployed — there is nothing to host or migrate separately.

It cannot simply be linked at `/assets/egrm/guide/`: that path is served by
nginx (and by the dev server) with `try_files $uri =404`, so a directory URL
like `.../docs/citizen/` 404s instead of falling back to `index.html`. This
renderer does that one fallback, and nothing else. The heavy files (JS, CSS,
screenshots) are emitted under `assetPrefix` = `/assets/egrm/guide/_next/`, so
they still go straight through nginx and never reach Python.
"""

import mimetypes
from functools import lru_cache
from pathlib import Path

import frappe
from frappe.website.page_renderers.base_renderer import BaseRenderer
from werkzeug.wrappers import Response

ROUTE = "guide"

# The HTML is regenerated on every deploy, so it must not be cached for long;
# the hashed asset files under /assets are the ones worth caching hard.
HTML_CACHE_CONTROL = "public, max-age=300"
FILE_CACHE_CONTROL = "public, max-age=3600"


@lru_cache(maxsize=1)
def guide_root() -> Path:
	"""Resolved once: the app path cannot change while the worker is alive."""
	return (Path(frappe.get_app_path("egrm")) / "public" / "guide").resolve()


class GuidePage(BaseRenderer):
	"""Render `/guide` and everything under it from the exported static site."""

	def can_render(self) -> bool:
		if self.path != ROUTE and not self.path.startswith(ROUTE + "/"):
			return False
		self.file_path = self._resolve()
		return self.file_path is not None

	def render(self) -> Response:
		data = self.file_path.read_bytes()
		mimetype = mimetypes.guess_type(self.file_path.name)[0] or "application/octet-stream"
		response = Response(data, mimetype=mimetype)
		response.headers["Cache-Control"] = (
			HTML_CACHE_CONTROL if self.file_path.suffix == ".html" else FILE_CACHE_CONTROL
		)
		return response

	def _resolve(self) -> Path | None:
		"""Map a request path to a file inside the export, or None."""
		root = guide_root()
		relative = self.path[len(ROUTE) :].strip("/")
		try:
			candidate = (root / relative).resolve()
		except OSError:
			return None

		# Refuse anything that escapes the export, whatever produced the path.
		if candidate != root and root not in candidate.parents:
			return None

		if candidate.is_dir():
			candidate = candidate / "index.html"
		elif not candidate.exists() and not candidate.suffix:
			# `/guide/docs/citizen` without the trailing slash.
			candidate = candidate.with_suffix(".html")

		return candidate if candidate.is_file() else None
