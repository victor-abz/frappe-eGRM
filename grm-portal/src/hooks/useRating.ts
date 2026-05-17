import { useCallback } from "react";
import { useFrappePostCall } from "frappe-react-sdk";

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

export function useRequestRatingCode() {
  const { call, result, loading, error, reset } = useFrappePostCall<{
    message: RequestRatingCodeResult;
  }>("egrm.api.rating.request_rating_code");

  const wrappedCall = useCallback(
    (tracking_code: string) => call({ tracking_code }),
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

export function useSubmitRating() {
  const { call, result, loading, error, reset } = useFrappePostCall<{
    message: SubmitRatingResult;
  }>("egrm.api.rating.submit_rating");

  const wrappedCall = useCallback(
    (params: {
      tracking_code: string;
      rating: number;
      comment?: string;
      code?: string;
    }) =>
      call({
        tracking_code: params.tracking_code,
        rating: String(params.rating),
        comment: params.comment || "",
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
