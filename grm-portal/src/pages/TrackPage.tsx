import { useState } from "react";
import { Search, CheckCircle, Clock, AlertCircle } from "lucide-react";
import { useTracking } from "@/hooks/useTracking";
import { useTranslate } from "@/hooks/useTranslate";

function statusBadge(status: string) {
  const s = status.toLowerCase();
  if (s.includes("resolv") || s.includes("closed") || s.includes("final")) {
    return "bg-green-100 text-green-700";
  }
  if (s.includes("pend") || s.includes("progress") || s.includes("initial")) {
    return "bg-orange-100 text-orange-700";
  }
  return "bg-blue-100 text-blue-700";
}

function statusIcon(status: string) {
  const s = status.toLowerCase();
  if (s.includes("resolv") || s.includes("closed") || s.includes("final")) {
    return <CheckCircle className="w-4 h-4" />;
  }
  if (s.includes("pend") || s.includes("progress") || s.includes("initial")) {
    return <Clock className="w-4 h-4" />;
  }
  return <AlertCircle className="w-4 h-4" />;
}

export default function TrackPage() {
  const { __ } = useTranslate();
  const [code, setCode] = useState("");
  const { call, result, loading, error, reset } = useTracking();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    reset();
    call({ tracking_code: code.trim() });
  };

  const data = result?.data;
  const isError = result?.status === "error" || error;

  return (
    <div className="max-w-md mx-auto px-4 py-12">
      <div className="text-center mb-8">
        <div className="inline-flex p-3 bg-primary-100 rounded-full mb-4">
          <Search className="w-6 h-6 text-primary-600" />
        </div>
        <h1 className="text-xl font-bold text-gray-900 mb-1">{__("Track Your Complaint")}</h1>
        <p className="text-sm text-grm-muted">{__("Enter your tracking code to check the status")}</p>
      </div>

      <form onSubmit={handleSubmit} className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder={__("Enter tracking code...")}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="w-full pl-10 pr-4 py-3 text-sm bg-white border border-gray-200 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder:text-gray-400"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !code.trim()}
          className="w-full mt-3 py-2.5 bg-primary-500 hover:bg-primary-600 disabled:bg-gray-300 text-white font-semibold text-sm rounded-xl shadow-md transition-colors"
        >
          {loading ? __("Searching...") : __("Track Complaint")}
        </button>
      </form>

      {/* Error */}
      {isError && (
        <p className="text-sm text-red-500 text-center">
          {result?.message || __("Complaint not found. Please check the tracking code.")}
        </p>
      )}

      {/* Result Card */}
      {data && (
        <div className="border border-grm-border rounded-xl overflow-hidden shadow-sm">
          <div className="px-4 py-3 bg-gray-50 border-b border-grm-border flex items-center justify-between">
            <span className="text-xs font-semibold text-grm-muted uppercase tracking-wider">{__("Tracking Result")}</span>
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
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <span className="text-xs text-grm-muted">{label}</span>
      <span className="text-sm font-medium text-gray-900">{value}</span>
    </div>
  );
}
