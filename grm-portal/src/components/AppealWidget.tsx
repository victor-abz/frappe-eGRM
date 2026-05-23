import { useEffect, useState } from "react";
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

  const handleRequestCode = async () => {
    await requestCode.call(trackingCode);
  };

  useEffect(() => {
    if (requestCode.result?.status === "success") setCodeSent(true);
  }, [requestCode.result]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!comment.trim()) return;
    await submit.call({
      tracking_code: trackingCode,
      comment,
      code: requiresCode ? code : "",
    });
  };

  useEffect(() => {
    if (submit.result?.status === "success" && !done) {
      setDone(true);
      setDoneDate(submit.result.appeal_date || null);
    }
  }, [submit.result, done]);

  if (done) {
    return (
      <div
        data-testid="appeal-done"
        className="mt-4 p-4 border border-grm-border rounded-xl bg-amber-50 flex items-start gap-3"
      >
        <CheckCircle2 className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {__("Your appeal has been recorded")}
          </div>
          {doneDate && (
            <div className="mt-0.5 text-xs text-gray-600">{doneDate}</div>
          )}
          {initialAppealReason && (
            <div className="mt-1 text-xs text-gray-700">{initialAppealReason}</div>
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
        className="mt-3 w-full py-2 text-sm font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 rounded-lg border border-amber-200 flex items-center justify-center gap-2"
      >
        <AlertTriangle className="w-4 h-4" />
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

      <textarea
        data-testid="appeal-comment"
        placeholder={__("Tell us why you are not satisfied")}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        rows={3}
        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
      />

      {requiresCode && (
        <div className="mt-3 space-y-2">
          <button
            type="button"
            data-testid="appeal-request-code"
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
              data-testid="appeal-code-input"
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
          data-testid="appeal-submit"
          disabled={
            submit.loading ||
            !comment.trim() ||
            (requiresCode && (!codeSent || code.length < 4))
          }
          className="w-full py-2.5 bg-amber-500 hover:bg-amber-600 disabled:bg-gray-300 text-white font-semibold text-sm rounded-xl shadow-md transition-colors"
        >
          {submit.loading ? __("Submitting...") : __("Submit appeal")}
        </button>
        {submit.result?.status === "error" && (
          <p className="mt-2 text-xs text-red-600" data-testid="appeal-error">
            {submit.result.message}
          </p>
        )}
      </form>
    </div>
  );
}
