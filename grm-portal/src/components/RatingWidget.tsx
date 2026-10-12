import { useEffect, useRef, useState } from "react";
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

  // A radio group is one stop in the tab order, not five: the arrow keys move
  // between the options once it has focus. Nothing in the browser does that
  // for a group built from buttons, so the roving tabindex and the key
  // handler below are what make it true.
  const starRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const focusedStar = stars || 1;

  const selectStar = (n: number) => {
    setStars(n);
    starRefs.current[n - 1]?.focus();
  };

  const handleStarKeyDown = (e: React.KeyboardEvent, n: number) => {
    switch (e.key) {
      case "ArrowRight":
      case "ArrowDown":
        e.preventDefault();
        selectStar(n === 5 ? 1 : n + 1);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        e.preventDefault();
        selectStar(n === 1 ? 5 : n - 1);
        break;
      case "Home":
        e.preventDefault();
        selectStar(1);
        break;
      case "End":
        e.preventDefault();
        selectStar(5);
        break;
      default:
        break;
    }
  };

  const handleRequestCode = async () => {
    await requestCode.call(trackingCode);
  };

  useEffect(() => {
    if (requestCode.result?.status === "success") setCodeSent(true);
  }, [requestCode.result]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stars) return;
    // aria-disabled keeps the button focusable so its hint stays
    // readable, which means the guard here is what actually blocks
    // a press, not the attribute.
    if (submit.loading) return;
    if (requiresCode && (!codeSent || code.length !== 6)) return;
    await submit.call({
      tracking_code: trackingCode,
      rating: stars,
      comment,
      code: requiresCode ? code : "",
    });
  };

  // Set the moment a submission succeeds, so the confirmation below is focused
  // only when it replaces the form the user was in -- never on a page that
  // simply loads already-rated.
  const justSubmitted = useRef(false);
  const doneRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (submit.result?.status === "success" && !done) {
      justSubmitted.current = true;
      setDone(true);
      setFinalRating(submit.result.rating || stars);
      onRated?.();
    }
  }, [submit.result, done, stars, onRated]);

  useEffect(() => {
    if (done && justSubmitted.current) doneRef.current?.focus();
  }, [done]);

  if (done) {
    return (
      <div
        ref={doneRef}
        tabIndex={-1}
        role="status"
        data-testid="rating-done"
        className="mt-4 p-4 border border-grm-border rounded-xl bg-green-50 flex items-start gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
      >
        <CheckCircle className="w-5 h-5 text-green-700 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {__("Thanks for your feedback")}
          </div>
          {/* The filled stars are a picture of the score. The score itself is
              written out so it does not depend on counting yellow shapes. */}
          <div className="mt-1 flex items-center gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <Star
                key={n}
                aria-hidden="true"
                className={`w-4 h-4 ${n <= finalRating ? "fill-amber-600 text-amber-700" : "text-gray-500"}`}
              />
            ))}
            <span className="ml-1 text-sm text-grm-secondary">
              {__("{0} out of 5", [String(finalRating)])}
            </span>
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
      <div className="text-sm font-semibold text-gray-900 mb-2" id="rating-label">
        {__("Rate this resolution")}
      </div>
      {/* A row of unlabelled star glyphs is invisible to a screen reader and
          too small for a thumb. Radio semantics give each star a name and a
          checked state; handleStarKeyDown supplies the arrow-key movement the
          role promises. */}
      <div
        className="flex items-center gap-1 mb-3"
        data-testid="rating-stars"
        role="radiogroup"
        aria-labelledby="rating-label"
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            ref={(el) => {
              starRefs.current[n - 1] = el;
            }}
            aria-checked={stars === n}
            aria-label={__("{0} out of 5", [String(n)])}
            data-testid={`rating-star-${n}`}
            tabIndex={n === focusedStar ? 0 : -1}
            onClick={() => setStars(n)}
            onKeyDown={(e) => handleStarKeyDown(e, n)}
            className="flex h-11 w-11 items-center justify-center rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
          >
            <Star
              aria-hidden="true"
              className={`w-7 h-7 ${n <= stars ? "fill-amber-600 text-amber-700" : "text-gray-500 hover:text-amber-600"}`}
            />
          </button>
        ))}
      </div>

      <label htmlFor="rating-comment" className="mb-1 block text-sm text-grm-secondary">
        {__("Add a short comment (optional)")}
      </label>
      <textarea
        id="rating-comment"
        name="rating-comment"
        data-testid="rating-comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={2}
        className="w-full px-3 py-2 text-base border border-grm-field rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-700"
      />

      {requiresCode && (
        <div className="mt-3 space-y-2">
          <button
            type="button"
            data-testid="rating-request-code"
            onClick={handleRequestCode}
            disabled={requestCode.loading}
            className="w-full min-h-[48px] py-2 text-sm font-medium text-primary-800 bg-primary-50 hover:bg-primary-100 rounded-lg border border-primary-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
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
            <>
              <label htmlFor="rating-code" className="block text-sm text-grm-secondary">
                {__("Enter the 6-digit code")}
              </label>
              <input
                id="rating-code"
                name="rating-code"
                type="text"
                data-testid="rating-code-input"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="w-full min-h-[48px] px-3 py-2 text-base tracking-widest border border-grm-field rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-700"
              />
            </>
          )}
          {requestCode.result?.status === "error" && (
            <p role="alert" className="text-sm font-medium text-red-700">
              {requestCode.result.message}
            </p>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-3">
        <button
          type="submit"
          data-testid="rating-submit"
          aria-disabled={
            submit.loading ||
            !stars ||
            (requiresCode && (!codeSent || code.length !== 6))
          }
          aria-describedby={!stars ? "rating-hint" : undefined}
          className="w-full min-h-[48px] py-2.5 bg-primary-700 hover:bg-primary-800 aria-disabled:bg-gray-600 aria-disabled:hover:bg-gray-600 aria-disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl shadow-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
        >
          {submit.loading ? __("Submitting...") : __("Submit rating")}
        </button>
        {!stars && (
          <p id="rating-hint" className="mt-2 text-sm text-grm-secondary">
            {__("Choose a star rating to continue.")}
          </p>
        )}
        {submit.result?.status === "error" && (
          <p role="alert" className="mt-2 text-sm font-medium text-red-700" data-testid="rating-error">
            {submit.result.message}
          </p>
        )}
      </form>
    </div>
  );
}
