import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, LayoutDashboard, LogIn, LogOut, User } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";
import type { PortalConfig } from "@/hooks/usePortalConfig";

const LOGIN_URL = "/login";
const STAFF_DASHBOARD_URL = "/app";

/**
 * Signing out had to be done from the Frappe desk, which meant a staff
 * member who opened the portal on a shared cell-office machine had no way
 * to end their session from the page they were actually on. Worse, the
 * portal never showed who was signed in, so there was nothing to tell them
 * a session was still live. This puts both on the page.
 */
async function logout(): Promise<void> {
  // frappe.handler.logout is whitelisted POST-only and CSRF-protected; the
  // token is injected into the page by www/grm-portal.html.
  const token = (window as unknown as { csrf_token?: string }).csrf_token ?? "";
  await fetch("/api/method/logout", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": token,
    },
  });
}

type Props = {
  config: PortalConfig;
  /** "bar" is the desktop navbar; "panel" is the stacked mobile menu. */
  variant: "bar" | "panel";
};

export default function AccountMenu({ config, variant }: Props) {
  const { __ } = useTranslate();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const isPanel = variant === "panel";

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      // Returning focus to the trigger is the part that is always skipped
      // and the part a keyboard user actually notices: without it focus
      // falls back to the top of the document.
      triggerRef.current?.focus();
    };
    const onPointer = (e: PointerEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>("a, button")?.focus();
  }, [open]);

  const handleSignOut = useCallback(async () => {
    setBusy(true);
    try {
      await logout();
    } catch {
      // A failed network call must not leave the page claiming to be
      // signed out, so fall through to a reload either way: the reloaded
      // page asks the server who is signed in and tells the truth.
    }
    window.location.assign("/grm-portal");
  }, []);

  // Guests get the plain call to action -- there is no identity to show
  // and no session to end.
  if (!config.is_authenticated) {
    return (
      <a
        href={LOGIN_URL}
        className={
          isPanel
            ? "mt-1 flex min-h-[48px] items-center justify-center gap-2 rounded-lg bg-primary-700 px-3 text-sm font-semibold text-white no-underline shadow-sm transition-colors hover:bg-primary-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-1"
            : "ml-2 flex min-h-[44px] items-center gap-1.5 rounded-lg bg-primary-700 px-3 text-sm font-semibold text-white no-underline shadow-sm transition-colors hover:bg-primary-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-1"
        }
      >
        <LogIn className={isPanel ? "h-5 w-5 shrink-0" : "h-3.5 w-3.5 shrink-0"} />
        <span>{__("Login")}</span>
      </a>
    );
  }

  const displayName = config.full_name || config.user;
  const menuId = `portal-account-menu-${variant}`;

  return (
    <div ref={wrapRef} className={isPanel ? "relative mt-1" : "relative ml-2"}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={menuId}
        className={
          isPanel
            ? "flex min-h-[48px] w-full items-center gap-3 rounded-lg border border-grm-field bg-white px-3 text-sm font-semibold text-grm-text transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
            : "flex min-h-[44px] items-center gap-1.5 rounded-lg border border-grm-field bg-white px-3 text-sm font-semibold text-grm-text transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
        }
      >
        <span
          aria-hidden="true"
          className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary-100 text-primary-800"
        >
          <User className="h-3.5 w-3.5" />
        </span>
        <span className="max-w-[9rem] truncate">{displayName}</span>
        <ChevronDown
          aria-hidden="true"
          className={`h-3.5 w-3.5 shrink-0 text-grm-secondary transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <div
        ref={panelRef}
        id={menuId}
        hidden={!open}
        className={
          isPanel
            ? "mt-1 rounded-lg border border-grm-border bg-white p-1 shadow-sm"
            : "absolute right-0 z-50 mt-1 w-64 rounded-lg border border-grm-border bg-white p-1 shadow-lg"
        }
      >
        <div className="border-b border-grm-border px-3 py-2">
          <p className="truncate text-sm font-semibold text-grm-text">{displayName}</p>
          <p className="truncate text-xs text-grm-secondary">{config.user}</p>
          {config.is_staff && (
            <p className="mt-1 text-xs font-medium text-primary-800">{__("Staff account")}</p>
          )}
        </div>

        {config.is_staff && (
          <a
            href={STAFF_DASHBOARD_URL}
            className="flex min-h-[44px] items-center gap-2.5 rounded-md px-3 text-sm font-medium text-grm-text no-underline transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
          >
            <LayoutDashboard className="h-4 w-4 shrink-0 text-grm-secondary" aria-hidden="true" />
            <span>{__("Go to Dashboard")}</span>
          </a>
        )}

        <button
          type="button"
          onClick={handleSignOut}
          disabled={busy}
          className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 text-left text-sm font-medium text-red-700 transition-colors hover:bg-red-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-700 disabled:opacity-60"
        >
          <LogOut className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{busy ? __("Signing out…") : __("Sign out")}</span>
        </button>
      </div>
    </div>
  );
}
