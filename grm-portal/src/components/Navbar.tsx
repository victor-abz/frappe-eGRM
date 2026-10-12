import { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ShieldCheck, BarChart3, Search, Send, FileText, Globe, Smartphone, Menu, X } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";
import { usePortalConfig } from "@/hooks/usePortalConfig";
import AccountMenu from "@/components/AccountMenu";

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

const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236B7280' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")";

export default function Navbar() {
  const location = useLocation();
  const { __, lang, setLang, languages } = useTranslate();
  const { config } = usePortalConfig();
  const [menuOpen, setMenuOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const links = ALL_LINKS.filter((link) => {
    if (link.gate === "dashboard") return config.show_dashboard;
    if (link.gate === "reports") return config.show_reports;
    return true;
  });

  const isActive = (to: string) =>
    to === "/grm-portal"
      ? location.pathname === "/grm-portal"
      : location.pathname.startsWith(to);

  // A page staff can see and the public cannot is marked as such. A silent
  // bypass means the only person who ever tests the switch is the one
  // person it never applies to, so an administrator who turns the public
  // dashboard off keeps seeing it and believes it is still published.
  const previewFor = (gate?: "dashboard" | "reports") =>
    gate === "dashboard" && config.dashboard_staff_preview
      ? __("Staff only")
      : gate === "reports" && config.reports_staff_preview
        ? __("Staff only")
        : null;

  // Navigating is the one thing the menu exists for, so it closes itself
  // rather than covering the page the visitor just asked for.
  useEffect(() => {
    setMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setMenuOpen(false);
      toggleRef.current?.focus();
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

  // Opening a panel without moving focus into it leaves a keyboard user
  // tabbing through the page behind the menu they just opened.
  useEffect(() => {
    if (!menuOpen) return;
    panelRef.current?.querySelector<HTMLElement>("a, button, select")?.focus();
  }, [menuOpen]);

  return (
    <nav
      ref={navRef}
      className="sticky top-0 z-50 border-b border-grm-border bg-white/95 backdrop-blur-sm"
      style={{ paddingTop: "env(safe-area-inset-top)" }}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-1 lg:py-3">
        <Link
          to="/grm-portal"
          className="flex min-h-[44px] min-w-0 items-center gap-2 text-sm font-bold text-grm-text no-underline"
        >
          <ShieldCheck className="h-5 w-5 shrink-0 text-primary-700" aria-hidden="true" />
          <span className="truncate">{__("GRM Portal")}</span>
        </Link>

        {/* Desktop: the full labelled bar. Labels only fit here once every
            link, the account button and the language picker are spelled out
            — below this the same row collapsed into anonymous icons. */}
        <div className="hidden items-center gap-1 lg:flex">
          {links.map((link) => {
            const preview = previewFor(link.gate);
            return (
              <Link
                key={link.to}
                to={link.to}
                aria-current={isActive(link.to) ? "page" : undefined}
                className={`flex min-h-[44px] items-center gap-1.5 rounded-lg px-3 text-sm font-medium no-underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-1 ${
                  isActive(link.to)
                    ? "bg-primary-50 text-primary-800"
                    : "text-grm-secondary hover:bg-gray-50"
                }`}
              >
                <link.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{__(link.label)}</span>
                {preview && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-900">
                    {preview}
                  </span>
                )}
              </Link>
            );
          })}

          <AccountMenu config={config} variant="bar" />

          <div className="ml-2 flex items-center gap-1.5 border-l border-grm-border pl-2">
            <Globe className="h-4 w-4 shrink-0 text-grm-secondary" aria-hidden="true" />
            <label htmlFor="portal-language-bar" className="sr-only">
              {__("Language")}
            </label>
            <select
              id="portal-language-bar"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="min-h-[44px] cursor-pointer appearance-none bg-transparent pr-5 text-sm font-medium text-grm-secondary transition-colors hover:text-grm-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
              style={{
                backgroundImage: SELECT_CHEVRON,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right center",
                backgroundSize: "14px 14px",
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
          ref={toggleRef}
          type="button"
          onClick={() => setMenuOpen((open) => !open)}
          aria-expanded={menuOpen}
          aria-controls="portal-mobile-menu"
          aria-label={menuOpen ? __("Close menu") : __("Open menu")}
          className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-grm-text transition-colors hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 lg:hidden"
        >
          {menuOpen ? <X className="h-6 w-6" aria-hidden="true" /> : <Menu className="h-6 w-6" aria-hidden="true" />}
        </button>
      </div>

      {/* Panel is always mounted so it can animate open and closed, and so a
          screen reader can reach it before the transition finishes. */}
      <div
        ref={panelRef}
        id="portal-mobile-menu"
        hidden={!menuOpen}
        className="overflow-hidden border-t border-grm-border bg-white shadow-lg lg:hidden"
      >
        <div
          className="flex flex-col gap-1 px-3 py-3"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}
        >
          {links.map((link) => {
            const preview = previewFor(link.gate);
            return (
              <Link
                key={link.to}
                to={link.to}
                aria-current={isActive(link.to) ? "page" : undefined}
                className={`flex min-h-[48px] items-center gap-3 rounded-lg px-3 text-sm font-medium no-underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                  isActive(link.to)
                    ? "bg-primary-50 text-primary-800"
                    : "text-grm-secondary hover:bg-gray-50 active:bg-gray-100"
                }`}
              >
                <link.icon className="h-5 w-5 shrink-0" aria-hidden="true" />
                <span>{__(link.label)}</span>
                {preview && (
                  <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-900">
                    {preview}
                  </span>
                )}
              </Link>
            );
          })}

          <AccountMenu config={config} variant="panel" />

          <div className="mt-2 border-t border-grm-border pt-3">
            <label
              htmlFor="portal-language"
              className="mb-1.5 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wide text-grm-secondary"
            >
              <Globe className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {__("Language")}
            </label>
            <select
              id="portal-language"
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="h-12 w-full appearance-none rounded-lg border border-grm-field bg-white px-3 pr-9 text-sm font-medium text-grm-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
              style={{
                backgroundImage: SELECT_CHEVRON,
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
