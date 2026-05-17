import { useCallback, useState } from "react";

export interface SubmitAppealResult {
  status: "success" | "error";
  message?: string;
  appeal_date?: string;
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

export function useSubmitAppeal() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SubmitAppealResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const call = useCallback(
    async (params: { tracking_code: string; comment: string; code?: string }) => {
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await postJson<SubmitAppealResult>(
          "/api/method/egrm.api.appeal.submit_appeal",
          {
            tracking_code: params.tracking_code,
            comment: params.comment,
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
