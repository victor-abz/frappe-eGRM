import { Smartphone, Download, AlertCircle, Loader2 } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";
import { useMobileApp } from "@/hooks/useMobileApp";

/** Bytes as megabytes, for a download the citizen may be paying for by the
 *  megabyte. Returns null when the server could not read the file's size. */
function formatSize(bytes: number | null | undefined): string | null {
  if (!bytes || bytes <= 0) return null;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DownloadAppPage() {
  const { __ } = useTranslate();
  const { info, isLoading, error } = useMobileApp();
  const fileSize = formatSize(info.file_size);

  return (
    <div className="mx-auto max-w-xl px-4 py-8">
      <div className="rounded-2xl border border-grm-border bg-white p-8 text-center shadow-sm">
        <div className="mb-5 inline-flex h-20 w-20 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-800">
          <Smartphone className="h-10 w-10" aria-hidden="true" />
        </div>

        <h1 className="mb-2 text-2xl font-bold text-grm-text">
          {__("eGRM Mobile App")}
        </h1>
        <p className="mb-6 text-sm leading-relaxed text-grm-secondary">
          {__(
            "Install the Android app to log grievances offline and sync when you have a connection."
          )}
        </p>

        {/* aria-busy alone. This wrapper also carried aria-live, which made
            every later change inside it -- a chart redrawing, a row
            appearing -- read out as though it were new. The loading and
            empty states below announce themselves with role="status", and
            that is the only thing worth announcing here. */}
        <div aria-busy={isLoading}>
          {isLoading && (
            <div className="flex items-center justify-center gap-2 py-6 text-grm-secondary" role="status">
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              <span className="text-sm">{__("Loading latest version…")}</span>
            </div>
          )}

          {!isLoading && Boolean(error) && (
            <div
              className="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-left text-sm text-red-800"
              role="alert"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{__("Could not load app information. Please try again later.")}</span>
            </div>
          )}

          {!isLoading && !error && info.available && info.download_url && (
            <>
              <p className="mb-5 text-sm text-grm-secondary">
                {__("Latest version")}:{" "}
                <code className="rounded bg-gray-100 px-2 py-0.5 text-sm text-grm-text">
                  {info.version_name}
                </code>
              </p>

              {/* "Download APK" alone, read out of a link list, does not say
                  what is being downloaded or how big it is -- but an
                  aria-label carrying that detail replaced the visible words
                  entirely, so anyone driving the page by voice said
                  "Download APK" and nothing happened (WCAG 2.5.3, Label in
                  Name). The visible words stay the start of the name and the
                  detail is appended after them. */}
              <a
                href={info.download_url}
                download
                className="inline-flex min-h-[44px] items-center justify-center gap-2 rounded-xl bg-primary-700 px-7 font-semibold text-white no-underline shadow-sm transition-colors hover:bg-primary-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
              >
                <Download className="h-5 w-5" aria-hidden="true" />
                {__("Download APK")}
                <span className="sr-only">
                  {" "}
                  {[__("eGRM Android app"), info.version_name, fileSize]
                    .filter(Boolean)
                    .join(", ")}
                </span>
              </a>

              {fileSize && (
                <p className="mt-2 text-sm text-grm-secondary" aria-hidden="true">
                  {fileSize}
                </p>
              )}

              <p className="mt-4 text-sm leading-relaxed text-grm-secondary">
                {__(
                  "Open the downloaded .apk file on your Android device to install. You may need to allow installs from unknown sources."
                )}
              </p>

              {info.release_notes && (
                <div className="mt-8 border-t border-grm-border pt-6 text-left">
                  <h2 className="mb-2 text-sm font-semibold text-grm-text">
                    {__("What's new")}
                  </h2>
                  {/* release_notes is a Text Editor field, which Frappe runs
                      through nh3.clean server-side on save
                      (base_document.py), so the stored HTML is already
                      sanitised. The styling is spelled out here because the
                      portal does not ship @tailwindcss/typography -- the
                      "prose" classes this used to carry resolved to nothing,
                      so every list and heading rendered unstyled. */}
                  <div
                    className="text-sm leading-relaxed text-grm-secondary [&_a]:text-primary-800 [&_a]:underline [&_h1]:mb-2 [&_h1]:mt-4 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-grm-text [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-grm-text [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:font-semibold [&_h3]:text-grm-text [&_li]:mb-1 [&_ol]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:mb-3 [&_strong]:font-semibold [&_strong]:text-grm-text [&_ul]:mb-3 [&_ul]:list-disc [&_ul]:pl-5"
                    dangerouslySetInnerHTML={{ __html: info.release_notes }}
                  />
                </div>
              )}
            </>
          )}

          {!isLoading && !error && !info.available && (
            <div
              className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-left text-sm text-amber-900"
              role="status"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <span>
                {info.message ||
                  __("The mobile app is not available yet. Please check back later.")}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
