import { useFrappePostCall } from "frappe-react-sdk";

export interface TrackingResult {
  status: "success" | "error";
  message?: string;
  data?: {
    tracking_code: string;
    status: string;
    category: string;
    submission_date: string;
    acknowledged_date?: string;
    resolution_date?: string;
    appeal_submitted: boolean;
  };
}

export function useTracking() {
  return useFrappePostCall<TrackingResult>(
    "egrm.api.public_tracking.track_complaint"
  );
}
