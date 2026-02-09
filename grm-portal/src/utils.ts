/**
 * Strip HTML tags from a string (e.g. Quill editor content).
 * Returns plain text only.
 */
export function stripHtml(html: string | undefined | null): string {
  if (!html) return "";
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent || "";
}
