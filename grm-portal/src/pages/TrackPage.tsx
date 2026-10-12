import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { useTracking } from "@/hooks/useTracking";
import { useTranslate } from "@/hooks/useTranslate";
import RatingWidget from "@/components/RatingWidget";
import AppealWidget from "@/components/AppealWidget";

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s.includes("resolv") || s.includes("closed") || s.includes("final")) {
    return "bg-green-100 text-green-800";
  }
  if (s.includes("pend") || s.includes("progress") || s.includes("initial")) {
    return "bg-orange-100 text-orange-900";
  }
  return "bg-blue-100 text-blue-800";
}

function statusIcon(status: string) {
  const s = status.toLowerCase();
  if (s.includes("resolv") || s.includes("closed") || s.includes("final")) {
    return <CheckCircle className="w-4 h-4" aria-hidden="true" />;
  }
  if (s.includes("pend") || s.includes("progress") || s.includes("initial")) {
    return <Clock className="w-4 h-4" aria-hidden="true" />;
  }
  return <AlertCircle className="w-4 h-4" aria-hidden="true" />;
}

export default function TrackPage() {
  const { __ } = useTranslate();
  const [searchParams] = useSearchParams();
  // The success screen hands the code over in the URL, so a citizen who has
  // just filed arrives at a looked-up result instead of an empty box they
  // would have to retype a code into that they may no longer have.
  const codeFromUrl = (searchParams.get("code") || "").trim();
  const [code, setCode] = useState(codeFromUrl);
  const [justRated, setJustRated] = useState(false);
  const { call, result, loading, error, reset } = useTracking();

  // Once, for whatever code the URL carried. A ref rather than a dependency
  // list because the citizen must stay free to edit the field and search
  // again without this firing a second time underneath them.
  const autoLookedUp = useRef(false);
  useEffect(() => {
    if (!codeFromUrl || autoLookedUp.current) return;
    autoLookedUp.current = true;
    call({ tracking_code: codeFromUrl });
  }, [codeFromUrl, call]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    reset();
    setJustRated(false);
    call({ tracking_code: code.trim() });
  };

  const data = result?.data;
  const isError = result?.status === "error" || error;

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="text-center mb-8">
        <div className="inline-flex p-3 bg-primary-100 rounded-full mb-4">
          <Search className="w-6 h-6 text-primary-800" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-bold text-gray-900 mb-1">{__("Track Your Complaint")}</h1>
        <p className="text-sm text-grm-secondary">{__("Enter your tracking code to check the status")}</p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        {/* The placeholder used to be the only label, so it disappeared the
            moment the citizen started typing and left nothing on screen or
            in the accessibility tree saying what the field wanted. */}
        <label htmlFor="tracking-code" className="mb-1.5 block text-sm font-medium text-grm-text">
          {__("Tracking code")}
        </label>
        <div className="relative">
          <Search
            className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-grm-secondary"
            aria-hidden="true"
          />
          <input
            id="tracking-code"
            name="tracking_code"
            type="text"
            inputMode="text"
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            placeholder={__("For example: RDAP-260803-5700")}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            aria-describedby="tracking-help"
            className="min-h-[48px] w-full rounded-xl border border-grm-field bg-white py-3 pl-10 pr-4 text-base shadow-sm placeholder:text-grm-secondary focus:border-transparent focus:outline-none focus:ring-2 focus:ring-primary-700"
          />
        </div>
        <p id="tracking-help" className="mt-1.5 text-sm text-grm-secondary">
          {__("This is the code you were given when the complaint was filed.")}
        </p>
        <button
          type="submit"
          disabled={loading || !code.trim()}
          className="mt-3 min-h-[48px] w-full rounded-xl bg-primary-700 text-base font-semibold text-white shadow-md transition-colors hover:bg-primary-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2 disabled:bg-gray-600"
        >
          {loading ? __("Searching...") : __("Track Complaint")}
        </button>
      </form>

      {/* Error. role="alert" so the result of pressing the button is
          announced; a silent paragraph change is invisible to a screen
          reader and easy to miss on a small screen. */}
      {isError && (
        <p role="alert" className="text-center text-sm font-medium text-red-700">
          {result?.message || __("Complaint not found. Please check the tracking code.")}
        </p>
      )}

      {/* Result Card. The card arrives below a button the citizen just
          pressed, with nothing else on the page changing, so it needs
          announcing -- but the card is not the thing to announce. Making the
          whole card live meant every later change inside it (a star pressed,
          an appeal form opened, a code field typed into) was read out as a
          fresh result. A one-line sibling carries the announcement instead,
          and the card is left as plain content the citizen can read at their
          own pace. */}
      {data && (
        <>
          <p className="sr-only" role="status">
            {__("Complaint {0} is {1}.", [data.tracking_code, __(data.status)])}
          </p>
        <div className="border border-grm-border rounded-xl overflow-hidden shadow-sm">
          <div className="px-4 py-3 bg-gray-50 border-b border-grm-border flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-grm-secondary">{__("Tracking Result")}</h2>
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${statusBadge(data.status)}`}>
              {statusIcon(data.status)}
              {__(data.status)}
            </span>
          </div>
          <div className="divide-y divide-grm-border">
            <Row label={__("Tracking Code")} value={data.tracking_code} />
            <Row label={__("Category")} value={__(data.category)} />
            <Row label={__("Submitted")} value={data.submission_date} />
            {data.acknowledged_date && <Row label={__("Acknowledged")} value={data.acknowledged_date} />}
            {data.resolution_date && <Row label={__("Resolved")} value={data.resolution_date} />}
            {data.appeal_submitted && (
              <Row label={__("Appeal")} value={__("Submitted")} />
            )}
          </div>

          {/* What was actually done. A bare "Resolved on <date>" gives the
              citizen nothing to accept, rate or appeal against, so the
              staff resolution note is shown in full rather than as a
              one-line Row. */}
          {data.resolution_text && (
            <div className="border-t border-grm-border bg-green-50/60 px-4 py-3">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-green-800">
                <CheckCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                {__("How this was resolved")}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
                {data.resolution_text}
              </p>
            </div>
          )}

          {data.appeal_submitted && data.appeal_reason && (
            <div className="border-t border-grm-border bg-blue-50/60 px-4 py-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-blue-800">
                {__("Reason for appeal")}
              </div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-gray-800">
                {data.appeal_reason}
              </p>
            </div>
          )}
          {(data.status.toLowerCase().includes("resolv") ||
            data.status.toLowerCase().includes("closed")) && (
            <div className="p-4 bg-gray-50 border-t border-grm-border">
              <RatingWidget
                trackingCode={data.tracking_code}
                contactChannel={data.contact_channel ?? null}
                initiallyRated={Boolean(data.rated)}
                initialRating={data.rating ?? 0}
                onRated={() => setJustRated(true)}
              />
              <AppealWidget
                trackingCode={data.tracking_code}
                contactChannel={data.contact_channel ?? null}
                alreadyRated={Boolean(data.rated) || justRated}
                initiallyAppealed={Boolean(data.appeal_submitted)}
                initialAppealDate={data.appeal_date ?? null}
                initialAppealReason={data.appeal_reason ?? ""}
              />
            </div>
          )}
        </div>
        </>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-2.5">
      <span className="text-sm text-grm-secondary">{label}</span>
      <span className="text-right text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}
