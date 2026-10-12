import { useMemo, useRef, useState } from "react";
import { Search, X } from "lucide-react";

export interface PickerOption {
  value: string;
  label: string;
}

/**
 * A single-choice picker that changes shape with the size of the list.
 *
 * A grid of cards is the right control for a handful of options: every choice
 * is visible, comparable and one tap away. It stops being the right control
 * somewhere around eight. RDAP already ships nine categories, which on a phone
 * is nine full-width cards the citizen must scroll past before they even reach
 * the Issue Type question below -- and an administrator can add more at any
 * time without touching this code. Past the threshold the same list gets a
 * filter box and a fixed-height scroller, so the step keeps its height no
 * matter how long the list grows, and finding "Bursary" costs one word rather
 * than a page of scrolling.
 *
 * The selected option is pinned above the scroller while a filter is active,
 * because a choice the user cannot see is a choice they cannot tell they made.
 */
export default function OptionPicker({
  idPrefix,
  label,
  options,
  value,
  onChange,
  __,
  emptyText,
  searchPlaceholder,
  threshold = 8,
}: {
  idPrefix: string;
  label: string;
  options: PickerOption[];
  value: string;
  onChange: (value: string) => void;
  __: (s: string) => string;
  emptyText: string;
  searchPlaceholder: string;
  threshold?: number;
}) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const labelId = `${idPrefix}-label`;

  const searchable = options.length > threshold;

  // Kinyarwanda and French labels carry diacritics that a citizen typing on a
  // phone keyboard will not reproduce. Strip them on both sides so "umushinga"
  // matches "Umushínga".
  const fold = (s: string) =>
    s
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return options;
    const q = fold(query);
    return options.filter((o) => fold(o.label).includes(q));
  }, [options, query, searchable]);

  const selected = options.find((o) => o.value === value);
  const selectedHidden = !!selected && !filtered.some((o) => o.value === value);

  const card = (o: PickerOption) => (
    <button
      key={o.value}
      type="button"
      aria-pressed={value === o.value}
      onClick={() => onChange(o.value)}
      className={`flex min-h-[44px] items-center text-left p-2.5 rounded-lg border text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
        value === o.value
          ? "border-primary-700 bg-primary-50 font-medium"
          : "border-grm-field hover:border-primary-700"
      }`}
    >
      {o.label}
    </button>
  );

  if (options.length === 0) {
    return (
      <>
        <h3 id={labelId} className="text-sm font-semibold text-gray-800 mb-2">
          {label}
        </h3>
        <p className="text-sm text-grm-secondary">{emptyText}</p>
      </>
    );
  }

  return (
    <>
      <div className="flex items-baseline justify-between mb-2">
        <h3 id={labelId} className="text-sm font-semibold text-gray-800">
          {label}
        </h3>
        {searchable && (
          <span className="text-xs text-grm-secondary">
            {__("{0} options").replace("{0}", String(options.length))}
          </span>
        )}
      </div>

      {searchable && (
        <div className="relative mb-2">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-grm-secondary"
            aria-hidden="true"
          />
          <input
            ref={inputRef}
            id={`${idPrefix}-search`}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              // Escape clears the filter instead of closing the dialog the
              // browser thinks it is in; nothing here is dismissible.
              if (e.key === "Escape" && query) {
                e.preventDefault();
                setQuery("");
              }
            }}
            placeholder={searchPlaceholder}
            aria-label={searchPlaceholder}
            aria-controls={`${idPrefix}-list`}
            autoComplete="off"
            className="w-full min-h-[44px] pl-9 pr-9 py-2 rounded-lg border border-grm-field text-sm placeholder:text-grm-secondary focus:outline-none focus:ring-2 focus:ring-primary-700 focus:border-primary-700"
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                inputRef.current?.focus();
              }}
              aria-label={__("Clear search")}
              className="absolute right-1 top-1/2 -translate-y-1/2 p-2 rounded-md text-grm-secondary hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          )}
        </div>
      )}

      {selectedHidden && (
        <div className="mb-2 flex items-center gap-2 text-sm text-grm-secondary">
          <span>{__("Selected:")}</span>
          <span className="font-medium text-primary-800">{selected?.label}</span>
        </div>
      )}

      {filtered.length === 0 ? (
        <p className="text-sm text-grm-secondary py-3" role="status">
          {__("No matches for “{0}”").replace("{0}", query.trim())}
        </p>
      ) : (
        <div
          id={`${idPrefix}-list`}
          className={`grid grid-cols-1 sm:grid-cols-2 gap-2 ${
            searchable ? "scroll-hint max-h-64 overflow-y-auto overscroll-contain pr-1 pb-1" : ""
          }`}
          role="group"
          aria-labelledby={labelId}
        >
          {filtered.map(card)}
        </div>
      )}

      {searchable && query.trim() && filtered.length > 0 && (
        <p className="sr-only" role="status" aria-live="polite">
          {__("{0} of {1} shown")
            .replace("{0}", String(filtered.length))
            .replace("{1}", String(options.length))}
        </p>
      )}
    </>
  );
}
