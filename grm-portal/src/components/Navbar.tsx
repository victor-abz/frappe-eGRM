import { Link, useLocation } from "react-router-dom";
import { ShieldCheck, BarChart3, Search, Send, FileText, Globe } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";

const links = [
  { to: "/grm-portal", label: "Home", icon: ShieldCheck },
  { to: "/grm-portal/dashboard", label: "Dashboard", icon: BarChart3 },
  { to: "/grm-portal/track", label: "Track", icon: Search },
  { to: "/grm-portal/submit", label: "Submit", icon: Send },
  { to: "/grm-portal/reports", label: "Reports", icon: FileText },
];

export default function Navbar() {
  const location = useLocation();
  const { __, lang, setLang, languages } = useTranslate();

  const isActive = (to: string) =>
    to === "/grm-portal"
      ? location.pathname === "/grm-portal"
      : location.pathname.startsWith(to);

  return (
    <nav className="sticky top-0 z-50 border-b border-grm-border bg-white/95 backdrop-blur-sm">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
        <Link to="/grm-portal" className="flex items-center gap-2 text-grm-text font-bold text-sm">
          <ShieldCheck className="h-5 w-5 text-teal-600" />
          <span>{__("GRM Portal")}</span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive(link.to)
                  ? "bg-teal-50 text-teal-700"
                  : "text-grm-secondary hover:bg-gray-50"
              }`}
            >
              <link.icon className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{__(link.label)}</span>
            </Link>
          ))}

          {/* Language Dropdown */}
          <div className="ml-2 flex items-center gap-1.5 border-l border-grm-border pl-2">
            <Globe className="h-3.5 w-3.5 text-grm-muted shrink-0" />
            <select
              value={lang}
              onChange={(e) => setLang(e.target.value)}
              className="appearance-none bg-transparent text-xs font-medium text-grm-secondary cursor-pointer pr-4 py-0.5 focus:outline-none hover:text-grm-text transition-colors"
              style={{ backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%237C7C7C' stroke-width='2'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E")`, backgroundRepeat: 'no-repeat', backgroundPosition: 'right center' }}
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
