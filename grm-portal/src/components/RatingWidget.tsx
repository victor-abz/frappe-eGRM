import { useEffect, useState } from "react";
import { Star, CheckCircle } from "lucide-react";
import { useRequestRatingCode, useSubmitRating } from "@/hooks/useRating";
import { useTranslate } from "@/hooks/useTranslate";

interface RatingWidgetProps {
  trackingCode: string;
  contactChannel: "phone" | "email" | null | undefined;
  initiallyRated: boolean;
  initialRating: number;
  onRated?: () => void;
}

export default function RatingWidget({
  trackingCode,
  contactChannel,
  initiallyRated,
  initialRating,
  onRated,
}: RatingWidgetProps) {
  const { __ } = useTranslate();
  const requiresCode = !!contactChannel;

  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [done, setDone] = useState(initiallyRated);
  const [finalRating, setFinalRating] = useState(initialRating || 0);

  const requestCode = useRequestRatingCode();
  const submit = useSubmitRating();

  const handleRequestCode = async () => {
    await requestCode.call(trackingCode);
  };

  useEffect(() => {
    if (requestCode.result?.status === "success") setCodeSent(true);
  }, [requestCode.result]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stars) return;
    await submit.call({
      tracking_code: trackingCode,
      rating: stars,
      comment,
      code: requiresCode ? code : "",
    });
  };

  useEffect(() => {
    if (submit.result?.status === "success" && !done) {
      setDone(true);
      setFinalRating(submit.result.rating || stars);
      onRated?.();
    }
  }, [submit.result, done, stars, onRated]);

  if (done) {
    return (
      <div
        data-testid="rating-done"
        className="mt-4 p-4 border border-grm-border rounded-xl bg-green-50 flex items-start gap-3"
      >
        <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {__("Thanks for your feedback")}
          </div>
          <div className="mt-1 flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star
                key={n}
                className={`w-4 h-4 ${n <= finalRating ? "fill-amber-400 text-amber-400" : "text-gray-300"}`}
              />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      data-testid="rating-widget"
      className="mt-4 p-4 border border-grm-border rounded-xl bg-white"
    >
      <div className="text-sm font-semibold text-gray-900 mb-2">
        {__("Rate this resolution")}
      </div>
      <div className="flex items-center gap-1 mb-3" data-testid="rating-stars">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`rating-star-${n}`}
            onClick={() => setStars(n)}
            className="p-0.5"
          >
            <Star
              className={`w-6 h-6 ${n <= stars ? "fill-amber-400 text-amber-400" : "text-gray-300 hover:text-amber-200"}`}
            />
          </button>
        ))}
      </div>

      <textarea
        data-testid="rating-comment"
        placeholder={__("Add a short comment (optional)")}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
      />

      {requiresCode && (
        <div className="mt-3 space-y-2">
          <button
            type="button"
            data-testid="rating-request-code"
            onClick={handleRequestCode}
            disabled={requestCode.loading}
            className="w-full py-2 text-sm font-medium text-primary-700 bg-primary-50 hover:bg-primary-100 rounded-lg border border-primary-200"
          >
            {requestCode.loading
              ? __("Sending...")
              : codeSent
                ? __("Resend verification code")
                : contactChannel === "phone"
                  ? __("Send code to my phone")
                  : __("Send code to my email")}
          </button>
          {codeSent && (
            <input
              type="text"
              data-testid="rating-code-input"
              inputMode="numeric"
              placeholder={__("Enter the 6-digit code")}
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          )}
          {requestCode.result?.status === "error" && (
            <p className="text-xs text-red-600">{requestCode.result.message}</p>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-3">
        <button
          type="submit"
          data-testid="rating-submit"
          disabled={
            submit.loading ||
            !stars ||
            (requiresCode && (!codeSent || code.length < 4))
          }
          className="w-full py-2.5 bg-primary-500 hover:bg-primary-600 disabled:bg-gray-300 text-white font-semibold text-sm rounded-xl shadow-md transition-colors"
        >
          {submit.loading ? __("Submitting...") : __("Submit rating")}
        </button>
        {submit.result?.status === "error" && (
          <p className="mt-2 text-xs text-red-600" data-testid="rating-error">
            {submit.result.message}
          </p>
        )}
      </form>
    </div>
  );
}
