import { Smartphone, Download, AlertCircle, Loader2 } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";
import { useMobileApp } from "@/hooks/useMobileApp";

export default function DownloadAppPage() {
  const { __ } = useTranslate();
  const { info, isLoading, error } = useMobileApp();

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl border border-grm-border p-8 shadow-sm text-center">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-emerald-50 text-emerald-600 mb-5">
          <Smartphone className="w-10 h-10" />
        </div>

        <h1 className="text-2xl font-bold text-grm-text mb-2">
          {__("eGRM Mobile App")}
        </h1>
        <p className="text-sm text-grm-muted mb-6">
          {__(
            "Install the Android app to log grievances offline and sync when you have a connection."
          )}
        </p>

        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-grm-muted py-6">
            <Loader2 className="w-4 h-4 animate-spin" />
            <span className="text-sm">{__("Loading latest version…")}</span>
          </div>
        )}

        {!isLoading && error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4 text-sm flex items-start gap-2 text-left">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{__("Could not load app information. Please try again later.")}</span>
          </div>
        )}

        {!isLoading && !error && info.available && info.download_url && (
          <>
            <p className="text-sm text-grm-muted mb-5">
              {__("Latest version")}:{" "}
              <code className="bg-gray-100 text-grm-text px-2 py-0.5 rounded text-xs">
                {info.version_name}
              </code>
            </p>

            <a
              href={info.download_url}
              download
              className="inline-flex items-center justify-center gap-2 bg-primary-600 hover:bg-primary-700 text-white font-semibold px-7 py-3 rounded-xl shadow-sm transition-colors no-underline"
            >
              <Download className="w-5 h-5" />
              {__("Download APK")}
            </a>

            <p className="text-xs text-grm-muted mt-4">
              {__(
                "Open the downloaded .apk file on your Android device to install. You may need to allow installs from unknown sources."
              )}
            </p>

            {info.release_notes && (
              <div className="mt-8 pt-6 border-t border-grm-border text-left">
                <h3 className="text-sm font-semibold text-grm-text mb-2">
                  {__("What's new")}
                </h3>
                <div
                  className="text-sm text-grm-secondary prose prose-sm max-w-none"
                  dangerouslySetInnerHTML={{ __html: info.release_notes }}
                />
              </div>
            )}
          </>
        )}

        {!isLoading && !error && !info.available && (
          <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4 text-sm flex items-start gap-2 text-left">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>
              {info.message ||
                __("The mobile app is not available yet. Please check back later.")}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
