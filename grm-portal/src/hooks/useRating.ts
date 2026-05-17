import { useCallback, useState } from "react";

export interface RequestRatingCodeResult {
  status: "success" | "error";
  message?: string;
  channel?: "phone" | "email";
}

export interface SubmitRatingResult {
  status: "success" | "error";
  message?: string;
  rating?: number;
  rating_submitted_at?: string;
}

async function postJson<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": (window as any).csrf_token || "",
    },
    body: JSON.stringify(body),
  });
  const json = await res.json();
  return (json.message ?? json) as T;
}

export function useRequestRatingCode() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RequestRatingCodeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const call = useCallback(async (tracking_code: string) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await postJson<RequestRatingCodeResult>(
        "/api/method/egrm.api.rating.request_rating_code",
        { tracking_code }
      );
      setResult(r);
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

export function useSubmitRating() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SubmitRatingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const call = useCallback(
    async (params: { tracking_code: string; rating: number; comment?: string; code?: string }) => {
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await postJson<SubmitRatingResult>(
          "/api/method/egrm.api.rating.submit_rating",
          {
            tracking_code: params.tracking_code,
            rating: String(params.rating),
            comment: params.comment || "",
            code: params.code || "",
          }
        );
        setResult(r);
      } catch (e: any) {
        setError(e?.message || "Network error");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  return { call, result, loading, error, reset };
}
