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
          <FileText className="w-6 h-6 text-primary-700" />
        </div>
        <h1 className="text-xl font-bold text-gray-900">{__("Public Reports")}</h1>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          <div className="animate-spin w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full mx-auto mb-2" />
          <p className="text-sm">{__("Loading reports...")}</p>
        </div>
      )}

      {!isLoading && reports.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <FileText className="w-10 h-10 mx-auto mb-3 opacity-50" />
          <p className="text-sm font-medium">{__("No reports available yet")}</p>
          <p className="text-xs mt-1">{__("Public reports will appear here once generated.")}</p>
        </div>
      )}

      {reports.length > 0 && (
        <div className="border border-grm-border rounded-xl overflow-hidden">
          {reports.map((report, idx) => (
            <div
              key={report.filename}
              className={`flex items-center justify-between px-4 py-3 ${idx % 2 === 1 ? "bg-gray-50" : ""} ${idx > 0 ? "border-t border-grm-border" : ""}`}
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-1.5 bg-primary-50 rounded-lg shrink-0">
                  <FileText className="w-4 h-4 text-primary-500" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-primary-100 text-primary-700">
                      {report.type}
                    </span>
                    <span className="text-xs text-grm-muted">{report.date}</span>
                  </div>
                  <p className="text-xs text-gray-500 truncate mt-0.5">
                    {report.project} &middot; {report.filename}
                  </p>
                </div>
              </div>
              <a
                href={report.url}
                target="_blank"
                rel="noopener noreferrer"
                className="p-2 text-grm-muted hover:text-primary-500 transition-colors shrink-0"
              >
                <Download className="w-4 h-4" />
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
