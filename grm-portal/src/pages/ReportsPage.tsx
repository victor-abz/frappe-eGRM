import { FileText, Download } from "lucide-react";
import { useFrappeGetCall } from "frappe-react-sdk";
import { useTranslate } from "@/hooks/useTranslate";

interface Report {
  filename: string;
  url: string;
  date: string;
  project: string;
  type: string;
}

export default function ReportsPage() {
  const { __ } = useTranslate();
  const { data, isLoading } = useFrappeGetCall<{ message: Report[] }>(
    "egrm.api.public_reports.get_public_reports"
  );

  const reports = data?.message || [];

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 bg-primary-100 rounded-lg">
          <FileText className="w-6 h-6 text-primary-800" aria-hidden="true" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">{__("Public Reports")}</h1>
      </div>

      {/* aria-busy alone. This wrapper also carried aria-live, which made
          every later change inside it -- a chart redrawing, a row
          appearing -- read out as though it were new. The loading and
          empty states below announce themselves with role="status", and
          that is the only thing worth announcing here. */}
      <div aria-busy={isLoading}>
        {isLoading && (
          <div className="text-center py-12 text-grm-secondary" role="status">
            <div className="animate-spin w-6 h-6 border-2 border-primary-700 border-t-transparent rounded-full mx-auto mb-2" />
            <p className="text-sm">{__("Loading reports...")}</p>
          </div>
        )}

        {!isLoading && reports.length === 0 && (
          <div className="text-center py-16 text-grm-secondary" role="status">
            <FileText className="w-10 h-10 mx-auto mb-3 text-gray-500" aria-hidden="true" />
            <p className="text-sm font-medium">{__("No reports available yet")}</p>
            <p className="text-sm mt-1">{__("Public reports will appear here once generated.")}</p>
          </div>
        )}

        {/* A list of files is a list: announced with its length rather than
            as a run of unrelated rows. */}
        {reports.length > 0 && (
          <ul className="border border-grm-border rounded-xl overflow-hidden list-none m-0 p-0">
            {reports.map((report, idx) => (
              <li
                key={report.filename}
                className={`flex items-center justify-between gap-3 px-4 py-3 ${idx % 2 === 1 ? "bg-gray-50" : ""} ${idx > 0 ? "border-t border-grm-border" : ""}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-1.5 bg-primary-50 rounded-lg shrink-0">
                    <FileText className="w-4 h-4 text-primary-800" aria-hidden="true" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-bold uppercase bg-primary-100 text-primary-800">
                        {report.type}
                      </span>
                      <span className="text-sm text-grm-secondary">{report.date}</span>
                    </div>
                    <p className="text-sm text-gray-700 truncate mt-0.5">
                      {report.project} &middot; {report.filename}
                    </p>
                  </div>
                </div>
                {/* An icon-only link reads as "link" and nothing else, so the
                    file it downloads is spelled out for anyone not looking at
                    the row it sits in. */}
                <a
                  href={report.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={__("Download {0}", [report.filename])}
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-grm-secondary hover:bg-gray-100 hover:text-primary-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
                >
                  <Download className="w-5 h-5" aria-hidden="true" />
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
