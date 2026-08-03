import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ShieldCheck, BarChart3, Search, Send, FileText, Globe, LogIn, LayoutDashboard, Smartphone, Menu, X } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";
import { usePortalConfig } from "@/hooks/usePortalConfig";

type NavLink = {
  to: string;
  label: string;
  icon: typeof ShieldCheck;
  gate?: "dashboard" | "reports";
};

const ALL_LINKS: NavLink[] = [
  { to: "/grm-portal", label: "Home", icon: ShieldCheck },
  { to: "/grm-portal/dashboard", label: "Dashboard", icon: BarChart3, gate: "dashboard" },
  { to: "/grm-portal/track", label: "Track", icon: Search },
  { to: "/grm-portal/submit", label: "Submit", icon: Send },
  { to: "/grm-portal/reports", label: "Reports", icon: FileText, gate: "reports" },
  { to: "/grm-portal/download", label: "Mobile App", icon: Smartphone },
];

const LOGIN_URL = "/login";
const STAFF_DASHBOARD_URL = "/app";

export default function Navbar() {
  const location = useLocation();
  const { __, lang, setLang, languages } = useTranslate();
  const { config } = usePortalConfig();
  const [menuOpen, setMenuOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  const links = ALL_LINKS.filter((link) => {
    if (link.gate === "dashboard") return config.show_dashboard;
    if (link.gate === "reports") return config.show_reports;
    return true;
  });

  const isActive = (to: string) =>
    to === "/grm-portal"
      ? location.pathname === "/grm-portal"
      : location.pathname.startsWith(to);

  // Navigating is the one thing the menu exists for, so it closes itself
  // rather than covering the page the visitor just asked for.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    const onPointer = (e: PointerEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [menuOpen]);

  const isStaff = config.is_authenticated && config.is_staff;
  const accountHref = isStaff ? STAFF_DASHBOARD_URL : LOGIN_URL;
  const AccountIcon = isStaff ? LayoutDashboard : LogIn;
  const accountLabel = isStaff ? __("Go to Dashboard") : __("Login");

  return (
    <nav
      ref={navRef}
      className="sticky top-0 z-50 border-b border-grm-border bg-white/95 backdrop-blur-sm"
      style={{ paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-1 lg:py-3">
        <Link
          to="/grm-portal"
          className="flex min-h-[44px] min-w-0 items-center gap-2 text-grm-text font-bold text-sm no-underline lg:min-h-0"
        >
          <ShieldCheck className="h-5 w-5 shrink-0 text-primary-500" />
          <span className="truncate">{__("GRM Portal")}</span>
        </Link>

        {/* Desktop: the full labelled bar. Labels only fit here once every
            link, the account button and the language picker are spelled out
            — below this the same row collapsed into anonymous icons. */}
        <div className="hidden items-center gap-1 lg:flex">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              aria-current={isActive(link.to) ? "page" : undefined}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium no-underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1 ${
                isActive(link.to)
                  ? "bg-primary-50 text-primary-700"
                  : "text-grm-secondary hover:bg-gray-50"
              }`}
            >
              <link.icon className="h-3.5 w-3.5 shrink-0" />
              <span>{__(link.label)}</span>
            </Link>
          ))}

          <a
            href={accountHref}
            className="ml-2 flex items-center gap-1.5 rounded-lg bg-primary-600 px-3 py-2 text-xs font-semibold text-white no-underline shadow-sm transition-colors hover:bg-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1"
          >
            <AccountIcon className="h-3.5 w-3.5 shrink-0" />
            <span>{accountLabel}</span>
          </a>

          <div className="ml-2 flex items-center gap-1.5 border-l border-grm-border pl-2">
            <Globe className="h-3.5 w-3.5 shrink-0 text-grm-muted" />
            <select
              aria-label={__("Language")}
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="cursor-pointer appearance-none bg-transparent py-1 pr-4 text-xs font-medium text-grm-secondary transition-colors hover:text-grm-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%237C7C7C' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right center",
              }}
            >
              {languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Mobile / tablet: one honest control instead of a row of glyphs. */}
        <button
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-controls="portal-mobile-menu"
          aria-label={menuOpen ? __("Close menu") : __("Open menu")}
          className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-grm-text transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 lg:hidden"
        >
          {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>
      </div>

      {/* Panel is always mounted so it can animate open and closed, and so a
          screen reader can reach it before the transition finishes. */}
      <div
        id="portal-mobile-menu"
        hidden={!menuOpen}
        className="overflow-hidden border-t border-grm-border bg-white shadow-lg lg:hidden"
      >
        <div
          className="flex flex-col gap-1 px-3 py-3"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              aria-current={isActive(link.to) ? "page" : undefined}
              className={`flex min-h-[48px] items-center gap-3 rounded-lg px-3 text-sm font-medium no-underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
                isActive(link.to)
                  ? "bg-primary-50 text-primary-700"
                  : "text-grm-secondary hover:bg-gray-50 active:bg-gray-100"
              }`}
            >
              <link.icon className="h-5 w-5 shrink-0" />
              <span>{__(link.label)}</span>
            </Link>
          ))}

          <a
            href={accountHref}
            className="mt-1 flex min-h-[48px] items-center justify-center gap-2 rounded-lg bg-primary-600 px-3 text-sm font-semibold text-white no-underline shadow-sm transition-colors hover:bg-primary-700 active:bg-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1"
          >
            <AccountIcon className="h-5 w-5 shrink-0" />
            <span>{accountLabel}</span>
          </a>

          <div className="mt-2 border-t border-grm-border pt-3">
            <label
              htmlFor="portal-language"
              className="mb-1.5 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-grm-muted"
            >
              <Globe className="h-3.5 w-3.5 shrink-0" />
              {__("Language")}
            </label>
            <select
              id="portal-language"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="h-12 w-full appearance-none rounded-lg border border-grm-border bg-white px-3 pr-9 text-sm font-medium text-grm-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
              style={{
                backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%237C7C7C' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 0.75rem center",
              }}
            >
              {languages.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </nav>
  );
}
