import { createBrowserRouter, Navigate } from "react-router-dom";
import PortalLayout from "./layouts/PortalLayout";
import HomePage from "./pages/HomePage";
import DashboardPage from "./pages/DashboardPage";
import TrackPage from "./pages/TrackPage";
import SubmitPage from "./pages/SubmitPage";
import ReportsPage from "./pages/ReportsPage";
import GatedRoute from "./components/GatedRoute";

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
      },
      {
        path: "dashboard",
        element: (
          <GatedRoute gate="dashboard">
            <DashboardPage />
          </GatedRoute>
        ),
      },
      {
        path: "track",
        element: <TrackPage />,
      },
      {
        path: "submit",
        element: <SubmitPage />,
      },
      {
        path: "reports",
        element: (
          <GatedRoute gate="reports">
            <ReportsPage />
          </GatedRoute>
        ),
      },
    ],
  },
]);

export default router;
