import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import PortalLayout from "./layouts/PortalLayout";
import HomePage from "./pages/HomePage";
import GatedRoute from "./components/GatedRoute";
import { useTranslate } from "./hooks/useTranslate";

// The home page is what a citizen with a slow connection lands on, so it
// ships in the first chunk. Everything else -- including the ~1,200-line
// submission wizard and the charting pages -- loads only when asked for,
// which is the difference between a two-second and a six-second first
// paint on the 3G connections this portal is actually used over.
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const TrackPage = lazy(() => import("./pages/TrackPage"));
const SubmitPage = lazy(() => import("./pages/SubmitPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const DownloadAppPage = lazy(() => import("./pages/DownloadAppPage"));

// Split out so the fallback can use the hook. This string was the one
// piece of UI text in the app that never reached __(), which made it the
// longest-lived English word on exactly the slow connections where the
// fallback is visible at all -- and the first thing a Kinyarwanda speaker
// saw on every lazy route.
function DeferredFallback() {
  const { __ } = useTranslate();
  return (
    <div
      className="flex min-h-[50vh] items-center justify-center text-sm text-grm-secondary"
      role="status"
      aria-live="polite"
    >
      {__("Loading…")}
    </div>
  );
}

function Deferred({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<DeferredFallback />}>{children}</Suspense>;
}

const router = createBrowserRouter([
  {
    path: "/",
    element: <Navigate to="/grm-portal" replace />,
  },
  {
    path: "/grm-portal",
    element: <PortalLayout />,
    children: [
      {
        index: true,
        element: <HomePage />,
        // Read by PortalLayout, which translates it into document.title.
        handle: { title: "Home" },
      },
      {
        path: "dashboard",
        element: (
          <GatedRoute gate="dashboard">
            <Deferred>
              <DashboardPage />
            </Deferred>
          </GatedRoute>
        ),
        handle: { title: "Dashboard" },
      },
      {
        path: "track",
        element: (
          <Deferred>
            <TrackPage />
          </Deferred>
        ),
        handle: { title: "Track a Complaint" },
      },
      {
        path: "submit",
        element: (
          <Deferred>
            <SubmitPage />
          </Deferred>
        ),
        handle: { title: "Submit a Grievance" },
      },
      {
        path: "reports",
        element: (
          <GatedRoute gate="reports">
            <Deferred>
              <ReportsPage />
            </Deferred>
          </GatedRoute>
        ),
        handle: { title: "Public Reports" },
      },
      {
        path: "download",
        element: (
          <Deferred>
            <DownloadAppPage />
          </Deferred>
        ),
        handle: { title: "Download the App" },
      },
    ],
  },
]);

export default router;
