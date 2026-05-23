import { useState, useCallback, useContext } from "react";
import { FrappeContext, FrappeConfig } from "frappe-react-sdk";

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
    appeal_date?: string | null;
    appeal_reason?: string;
    contact_channel?: "phone" | "email" | null;
    rating?: number;
    rated?: boolean;
    rating_submitted_at?: string | null;
  };
}

export function useTracking() {
  const { call } = useContext(FrappeContext) as FrappeConfig;
  const [result, setResult] = useState<TrackingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const callTrack = useCallback(
    async (params: { tracking_code: string }) => {
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const resp = await call.get<{ message: TrackingResult }>(
          "egrm.api.public_tracking.track_complaint",
          params
        );
        setResult(resp?.message ?? null);
      } catch (e: any) {
        setError(e?.message || "Network error");
      } finally {
        setLoading(false);
      }
    },
    [call]
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { call: callTrack, result, loading, error, reset };
}
