import { createBrowserRouter, Navigate } from "react-router-dom";
import PortalLayout from "./layouts/PortalLayout";
import HomePage from "./pages/HomePage";
import DashboardPage from "./pages/DashboardPage";
import TrackPage from "./pages/TrackPage";
import SubmitPage from "./pages/SubmitPage";
import ReportsPage from "./pages/ReportsPage";

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
        element: <DashboardPage />,
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
        element: <ReportsPage />,
      },
    ],
  },
]);

export default router;
