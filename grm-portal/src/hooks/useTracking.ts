import { useState, useCallback } from "react";

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
  const [result, setResult] = useState<TrackingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const call = useCallback(async (params: { tracking_code: string }) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const qs = new URLSearchParams({ tracking_code: params.tracking_code }).toString();
      const res = await fetch(
        `/api/method/egrm.api.public_tracking.track_complaint?${qs}`
      );
      const json = await res.json();
      setResult(json.message);
    } catch (e: any) {
      setError(e?.message || "Network error");
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { call, result, loading, error, reset };
}
