import { Outlet } from "react-router-dom";
import Navbar from "@/components/Navbar";
import { useTranslate } from "@/hooks/useTranslate";

export default function PortalLayout() {
  const { __ } = useTranslate();

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <Navbar />
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-grm-border py-6 text-center text-xs text-grm-muted">
        {__("Grievance Redress Mechanism")} &mdash; {__("Public Portal")}
      </footer>
    </div>
  );
}
