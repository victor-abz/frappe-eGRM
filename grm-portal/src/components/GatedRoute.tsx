import { Navigate } from "react-router-dom";
import { usePortalConfig } from "@/hooks/usePortalConfig";

type Props = {
  gate: "dashboard" | "reports";
  children: React.ReactNode;
};

export default function GatedRoute({ gate, children }: Props) {
  const { config, isLoading } = usePortalConfig();

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-grm-muted">
        Loading…
      </div>
    );
  }

  const allowed = gate === "dashboard" ? config.show_dashboard : config.show_reports;
  if (!allowed) {
    return <Navigate to="/grm-portal" replace />;
  }

  return <>{children}</>;
}
