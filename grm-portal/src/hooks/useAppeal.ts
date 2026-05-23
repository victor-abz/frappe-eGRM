import { useCallback } from "react";
import { useFrappePostCall } from "frappe-react-sdk";

export interface SubmitAppealResult {
  status: "success" | "error";
  message?: string;
  appeal_date?: string;
}

export function useSubmitAppeal() {
  const { call, result, loading, error, reset } = useFrappePostCall<{
    message: SubmitAppealResult;
  }>("egrm.api.appeal.submit_appeal");

  const wrappedCall = useCallback(
    (params: { tracking_code: string; comment: string; code?: string }) =>
      call({
        tracking_code: params.tracking_code,
        comment: params.comment,
        code: params.code || "",
      }),
    [call]
  );

  return {
    call: wrappedCall,
    result: result?.message ?? null,
    loading,
    error: error ? error.message || "Network error" : null,
    reset,
  };
}
