import { Link } from "react-router-dom";
import { EyeOff } from "lucide-react";
import { usePortalConfig } from "@/hooks/usePortalConfig";
import { useTranslate } from "@/hooks/useTranslate";

type Props = {
  gate: "dashboard" | "reports";
  children: React.ReactNode;
};

export default function GatedRoute({ gate, children }: Props) {
  const { config, isLoading } = usePortalConfig();
  const { __ } = useTranslate();

  if (isLoading) {
    return (
      <div
        className="flex min-h-[40vh] items-center justify-center text-sm text-grm-secondary"
        role="status"
      >
        {__("Loading…")}
      </div>
    );
  }

  const allowed = gate === "dashboard" ? config.show_dashboard : config.show_reports;

  // A bookmarked or shared link to a page an administrator has switched off
  // used to bounce silently to the home page, which reads as a broken link.
  // Saying so costs nothing -- the flag is not a secret, only the data is --
  // and it tells a colleague exactly what to ask the administrator for.
  if (!allowed) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <div className="mb-4 inline-flex rounded-full bg-gray-100 p-3">
          <EyeOff className="h-6 w-6 text-grm-secondary" aria-hidden="true" />
        </div>
        <h1 className="mb-2 text-xl font-bold text-gray-900">
          {gate === "dashboard"
            ? __("The public dashboard is turned off")
            : __("Public reports are turned off")}
        </h1>
        <p className="mb-6 text-sm leading-relaxed text-grm-secondary">
          {__(
            "An administrator has not published this page. If you need the figures, ask your GRM administrator to enable it."
          )}
        </p>
        <Link
          to="/grm-portal"
          className="inline-flex min-h-[44px] items-center rounded-xl bg-primary-700 px-5 font-semibold text-white transition-colors hover:bg-primary-800"
        >
          {__("Back to the portal")}
        </Link>
      </div>
    );
  }

  return <>{children}</>;
}
