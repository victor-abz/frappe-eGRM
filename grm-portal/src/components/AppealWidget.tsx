import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { useRequestRatingCode } from "@/hooks/useRating";
import { useSubmitAppeal } from "@/hooks/useAppeal";
import { useTranslate } from "@/hooks/useTranslate";

interface AppealWidgetProps {
  trackingCode: string;
  contactChannel: "phone" | "email" | null | undefined;
  alreadyRated: boolean;
  initiallyAppealed: boolean;
  initialAppealDate?: string | null;
  initialAppealReason?: string;
}

export default function AppealWidget({
  trackingCode,
  contactChannel,
  alreadyRated,
  initiallyAppealed,
  initialAppealDate,
  initialAppealReason,
}: AppealWidgetProps) {
  const { __ } = useTranslate();
  // Code is required only when the citizen is identified AND has not already
  // rated (which would have proved verification).
  const requiresCode = !!contactChannel && !alreadyRated;

  const [opened, setOpened] = useState(false);
  const [comment, setComment] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [done, setDone] = useState(initiallyAppealed);
  const [doneDate, setDoneDate] = useState<string | undefined | null>(
    initialAppealDate
  );

  const requestCode = useRequestRatingCode();
  const submit = useSubmitAppeal();
  const commentRef = useRef<HTMLTextAreaElement>(null);

  // The button that opened the form is gone once the form replaces it, so
  // focus would otherwise fall back to the top of the document.
  useEffect(() => {
    if (opened) commentRef.current?.focus();
  }, [opened]);

  const handleRequestCode = async () => {
    await requestCode.call(trackingCode);
  };

  useEffect(() => {
    if (requestCode.result?.status === "success") setCodeSent(true);
  }, [requestCode.result]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) return;
    // aria-disabled keeps the button focusable so its hint stays
    // readable, which means the guard here is what actually blocks
    // a press, not the attribute.
    if (submit.loading) return;
    if (requiresCode && (!codeSent || code.length !== 6)) return;
    await submit.call({
      tracking_code: trackingCode,
      comment,
      code: requiresCode ? code : "",
    });
  };

  // Set the moment a submission succeeds, so the confirmation below is focused
  // only when it replaces the form the user was in -- never on a page that
  // simply loads with an appeal already on file.
  const justSubmitted = useRef(false);
  const doneRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (submit.result?.status === "success" && !done) {
      justSubmitted.current = true;
      setDone(true);
      setDoneDate(submit.result.appeal_date || null);
    }
  }, [submit.result, done]);

  useEffect(() => {
    if (done && justSubmitted.current) doneRef.current?.focus();
  }, [done]);

  if (done) {
    return (
      <div
        ref={doneRef}
        tabIndex={-1}
        role="status"
        data-testid="appeal-done"
        className="mt-4 p-4 border border-grm-border rounded-xl bg-amber-50 flex items-start gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
      >
        <CheckCircle2 className="w-5 h-5 text-amber-800 mt-0.5 flex-shrink-0" aria-hidden="true" />
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {__("Your appeal has been recorded")}
          </div>
          {doneDate && (
            <div className="mt-0.5 text-sm text-gray-700">{doneDate}</div>
          )}
          {initialAppealReason && (
            <div className="mt-1 text-sm text-gray-800">{initialAppealReason}</div>
          )}
        </div>
      </div>
    );
  }

  if (!opened) {
    return (
      <button
        type="button"
        data-testid="appeal-open"
        onClick={() => setOpened(true)}
        className="mt-3 w-full min-h-[48px] py-2 text-sm font-medium text-amber-900 bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-700 flex items-center justify-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
      >
        <AlertTriangle className="w-4 h-4" aria-hidden="true" />
        {__("Not satisfied? Submit an appeal")}
      </button>
    );
  }

  return (
    <div
      data-testid="appeal-widget"
      className="mt-4 p-4 border border-grm-border rounded-xl bg-white"
    >
      <div className="text-sm font-semibold text-gray-900 mb-2">
        {__("Submit an appeal")}
      </div>

      <label htmlFor="appeal-comment" className="mb-1 block text-sm text-grm-secondary">
        {__("Tell us why you are not satisfied")}
      </label>
      <textarea
        id="appeal-comment"
        name="appeal-comment"
        ref={commentRef}
        data-testid="appeal-comment"
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
        className="w-full px-3 py-2 text-base border border-grm-field rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-700"
      />

      {requiresCode && (
        <div className="mt-3 space-y-2">
          <button
            type="button"
            data-testid="appeal-request-code"
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
              <label htmlFor="appeal-code" className="block text-sm text-grm-secondary">
                {__("Enter the 6-digit code")}
              </label>
              <input
                id="appeal-code"
                name="appeal-code"
                type="text"
                data-testid="appeal-code-input"
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
          data-testid="appeal-submit"
          aria-disabled={
            submit.loading ||
            !comment.trim() ||
            (requiresCode && (!codeSent || code.length !== 6))
          }
          aria-describedby={!comment.trim() ? "appeal-hint" : undefined}
          className="w-full min-h-[48px] py-2.5 bg-amber-700 hover:bg-amber-800 aria-disabled:bg-gray-600 aria-disabled:hover:bg-gray-600 aria-disabled:cursor-not-allowed text-white font-semibold text-sm rounded-xl shadow-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
        >
          {submit.loading ? __("Submitting...") : __("Submit appeal")}
        </button>
        {!comment.trim() && (
          <p id="appeal-hint" className="mt-2 text-sm text-grm-secondary">
            {__("Tell us why you are not satisfied to continue.")}
          </p>
        )}
        {submit.result?.status === "error" && (
          <p role="alert" className="mt-2 text-sm font-medium text-red-700" data-testid="appeal-error">
            {submit.result.message}
          </p>
        )}
      </form>
    </div>
  );
}
