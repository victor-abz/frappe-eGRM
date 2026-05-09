"""Step 9 (Users) Playwright walker.

Pins every selector the wizard's Step 9 UI exposes so future UI changes
are a one-line fix here, not a 14-suite migration.

Flow (mirrors what a human does):

    1. Open the wizard at Step 9 for the project
    2. Write the CSV to a temp file
    3. Upload it via the file input (#grm-u-file)
    4. Click Validate (#grm-u-validate); assert "Detected N valid rows"
    5. Click Create Users (#grm-u-import); assert "Created N users"
    6. Capture preview/after screenshots
    7. Re-fetch created users + activation codes via the same RPC the
       button just called (idempotent — bulk_create is keyed by email)
    8. API-set the known per-project password for each user (the UI
       never exposes a password field; passwords would otherwise be
       auto-generated random and downstream suites couldn't auth)

Public API:
    walk_step9(page, api_session, project_code, csv_text,
               default_password, role_to_email) -> dict

Returns a dict shaped like wizard_state[i].users:
    {
        "default_password": "...",
        "created_at": "ISO8601",
        "by_role": {role: {"email": str, "activation_code": str}},
        "step9_evidence": {...},
    }

Raises Step9WalkerError on any UI / API mismatch.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from _common import ART, PROJECT_USER_TEMPLATE, SITE


SCREENSHOT_DIR = ART / "screenshots" / "wizard_steps"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class Step9WalkerError(RuntimeError):
    """Raised when the Step 9 walkthrough fails any precondition."""


# --- Selector pins (single source of truth) -------------------------------

SEL_STEP9_TABLE_WRAP   = "#grm-step9-table-wrap"  # legacy step9 (Issue Categories pre-Phase B)
SEL_USERS_CSV_TAB      = 'a[href="#grm-u-csv"]'
SEL_FILE_INPUT         = "#grm-u-file"
SEL_VALIDATE_BTN       = "#grm-u-validate"
SEL_IMPORT_BTN         = "#grm-u-import"
SEL_RESULT_DIV         = "#grm-u-result"
SEL_RESULT_INFO_ALERT  = "#grm-u-result .alert-info"
SEL_RESULT_SUCCESS     = "#grm-u-result .alert-success"
SEL_RESULT_DANGER      = "#grm-u-result .alert-danger"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _open_wizard_at_step(page, project_code: str, step: int = 9) -> None:
    url = f"{SITE}/app/grm-project-wizard?project={project_code}&step={step}"
    page.goto(url, wait_until="networkidle", timeout=30000)
    # The Users panel renders inside the wizard body. We wait for the
    # CSV-tab anchor to be present as the proxy for "Step 9 is rendered".
    page.wait_for_selector(SEL_FILE_INPUT, timeout=20000)


def _upload_csv(page, csv_text: str) -> Path:
    """Write CSV to a NamedTemporaryFile and upload via the file input."""
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, prefix="step9_")
    f.write(csv_text)
    f.close()
    csv_path = Path(f.name)
    page.set_input_files(SEL_FILE_INPUT, str(csv_path))
    return csv_path


def _click_validate_and_assert(page, expected_rows: int) -> int:
    page.click(SEL_VALIDATE_BTN)
    # Validate either renders an .alert-info ("Detected N valid rows")
    # or an .alert-danger (per-row errors). Wait for either, decide.
    deadline = time.time() + 20
    while time.time() < deadline:
        if page.locator(SEL_RESULT_DANGER).count():
            txt = page.locator(SEL_RESULT_DANGER).inner_text()
            raise Step9WalkerError(f"validate reported errors: {txt!r}")
        if page.locator(SEL_RESULT_INFO_ALERT).count():
            txt = page.locator(SEL_RESULT_INFO_ALERT).inner_text()
            # Format: "Detected {N} valid rows."
            import re
            m = re.search(r"Detected\s+(\d+)\s+valid\s+rows", txt, re.IGNORECASE)
            if not m:
                raise Step9WalkerError(f"could not parse validate result: {txt!r}")
            n = int(m.group(1))
            if n != expected_rows:
                raise Step9WalkerError(
                    f"validate row count mismatch: got {n} expected {expected_rows}"
                )
            return n
        page.wait_for_timeout(250)
    raise Step9WalkerError("timeout waiting for validate result")


def _click_import_and_assert(page, expected_rows: int) -> tuple[int, int]:
    """Click Create Users; assert success alert appears with N created."""
    page.click(SEL_IMPORT_BTN)
    deadline = time.time() + 60
    while time.time() < deadline:
        if page.locator(SEL_RESULT_DANGER).count():
            txt = page.locator(SEL_RESULT_DANGER).inner_text()
            raise Step9WalkerError(f"import reported errors: {txt!r}")
        if page.locator(SEL_RESULT_SUCCESS).count():
            txt = page.locator(SEL_RESULT_SUCCESS).inner_text()
            import re
            m = re.search(
                r"Created\s+(\d+)\s+users.*?Failures:\s*(\d+)", txt, re.IGNORECASE
            )
            if not m:
                raise Step9WalkerError(f"could not parse import result: {txt!r}")
            created = int(m.group(1))
            failures = int(m.group(2))
            if created != expected_rows or failures != 0:
                raise Step9WalkerError(
                    f"import counts mismatch: created={created} failures={failures} "
                    f"expected created={expected_rows} failures=0"
                )
            return (created, failures)
        page.wait_for_timeout(250)
    raise Step9WalkerError("timeout waiting for import result")


def _capture(page, path: Path) -> None:
    page.screenshot(path=str(path), full_page=True)
    txt = path.with_suffix(".txt")
    try:
        txt.write_text(page.locator("body").inner_text())
    except Exception:
        pass  # text sidecar is best-effort


def _api_post_form(api_session, path: str, data: dict, timeout: int = 60) -> dict:
    """POST as form-encoded with auto-JSON-encoding for list/dict values
    (Frappe's REST quirk — see _common._form_encode_safe)."""
    enc: dict = {}
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            enc[k] = json.dumps(v, default=str)
        else:
            enc[k] = v
    r = api_session.post(f"{SITE}{path}", data=enc, timeout=timeout)
    if r.status_code != 200:
        raise Step9WalkerError(f"{path} -> HTTP {r.status_code} {r.text[:300]}")
    try:
        return r.json()
    except Exception as e:
        raise Step9WalkerError(f"{path} non-JSON body: {e} {r.text[:200]}")


def _fetch_activation_codes(api_session, project_code: str) -> dict[str, str]:
    """Pull the activation codes table for this project. The wizard's
    'Activation Codes' tab uses export_activation_codes which returns a
    CSV string; we ask the same endpoint and parse it."""
    body = _api_post_form(
        api_session,
        "/api/method/egrm.egrm.page.grm_project_wizard.grm_project_wizard."
        "export_activation_codes",
        {"project": project_code},
    )
    csv_text = body.get("message") or ""
    out: dict[str, str] = {}
    if not csv_text.strip():
        return out
    lines = [ln for ln in csv_text.splitlines() if ln.strip()]
    if not lines:
        return out
    header = [c.strip().lower() for c in lines[0].split(",")]
    try:
        i_email = header.index("email")
    except ValueError:
        return out
    code_idx = None
    for cand in ("activation_code", "code"):
        if cand in header:
            code_idx = header.index(cand)
            break
    if code_idx is None:
        return out
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split(",")]
        if len(cells) > max(i_email, code_idx):
            out[cells[i_email]] = cells[code_idx]
    return out


def _api_set_password(api_session, email: str, password: str) -> None:
    """Set a known password for a freshly-created user. Uses
    frappe.client.set_value on the User doc. The Administrator session
    has permission to do this."""
    body = _api_post_form(
        api_session,
        "/api/method/frappe.core.doctype.user.user.update_password",
        {"new_password": password, "user": email},
    )
    # Some Frappe versions return {} on success; only treat explicit
    # exception payload as failure.
    msg = body.get("exc") if isinstance(body, dict) else None
    if msg:
        raise Step9WalkerError(f"update_password({email}) failed: {msg}")


def _api_enable_user(api_session, email: str) -> None:
    """Make sure the user is `enabled=1` so they can log in."""
    body = _api_post_form(
        api_session,
        "/api/method/frappe.client.set_value",
        {"doctype": "User", "name": email, "fieldname": "enabled", "value": 1},
    )
    if body.get("exc"):
        raise Step9WalkerError(f"enable({email}) failed: {body.get('exc')}")


def walk_step9(page, api_session, project_code: str,
               csv_text: str, default_password: str,
               role_to_email: dict[str, str]) -> dict[str, Any]:
    """Drive the wizard Step 9 UI end-to-end for ONE project.

    `page`             — Playwright page logged in as Administrator
    `api_session`      — requests.Session logged in as Administrator
    `project_code`     — e.g. "RW-WB"
    `csv_text`         — CSV string from `_common.build_step9_csv`
    `default_password` — known password we'll API-set after UI create,
                         since the UI doesn't expose a password field
    `role_to_email`    — slot -> email map from `_common.build_step9_csv`
    """
    expected = len(PROJECT_USER_TEMPLATE)

    _open_wizard_at_step(page, project_code, step=9)
    csv_path = _upload_csv(page, csv_text)
    try:
        _click_validate_and_assert(page, expected_rows=expected)

        preview_png = SCREENSHOT_DIR / f"wizard_step_09_{project_code}.png"
        _capture(page, preview_png)

        created, failures = _click_import_and_assert(page, expected_rows=expected)

        after_png = SCREENSHOT_DIR / f"wizard_step_09_{project_code}_after.png"
        _capture(page, after_png)
    finally:
        try:
            csv_path.unlink()
        except Exception:
            pass

    # API-set the known password + ensure enabled, for every created user.
    # The wizard auto-generated random passwords; we overwrite with the
    # known per-project default so downstream suites can `login(email,
    # default_password)` deterministically.
    for role, email in role_to_email.items():
        _api_enable_user(api_session, email)
        _api_set_password(api_session, email, default_password)

    activation_codes = _fetch_activation_codes(api_session, project_code)

    by_role: dict[str, dict[str, str]] = {}
    for role, email in role_to_email.items():
        by_role[role] = {
            "email": email,
            "activation_code": activation_codes.get(email, ""),
        }

    return {
        "default_password": default_password,
        "created_at": _now_iso(),
        "by_role": by_role,
        "step9_evidence": {
            "csv_sha1": _sha1(csv_text),
            "preview_screenshot": str(preview_png.relative_to(ART)),
            "after_screenshot":   str(after_png.relative_to(ART)),
            "bulk_create_response": {
                "created": created,
                "errors": [],
            },
        },
    }
