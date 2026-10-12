import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { FrappeContext, FrappeConfig } from "frappe-react-sdk";

type Translations = Record<string, string>;

export interface LanguageOption {
  code: string;
  name: string;
}

interface TranslateContextValue {
  __: (key: string, replacements?: string[]) => string;
  lang: string;
  setLang: (lang: string) => void;
  languages: LanguageOption[];
  isLoading: boolean;
}

// Singleton caches — shared across all components, survive re-renders
let translationCache: Record<string, Translations> = {};
// Languages whose cache entry is the inlined subset rather than the whole
// dictionary. Those are good enough to render the first paint from, but they
// cover only the literals the extractor could see -- not the strings that
// arrive as data (issue statuses, categories, issue types, region names), and
// not any literal the extractor missed. A partial entry must therefore still
// trigger the fetch, which is exactly what the old plain presence check in the
// fetch effect stopped it doing.
const partialLangs = new Set<string>();
let languagesCache: LanguageOption[] | null = null;

// Last-resort list, used only when the Language lookup itself fails. The
// enabled rows of the `Language` doctype are the source of truth — this
// mirrors the set that egrm/patches/v16_0/restrict_enabled_languages.py
// enables, so a failed request degrades to the same options rather than
// offering a locale the backend has switched off and has no translations for.
const FALLBACK_LANGUAGES: LanguageOption[] = [
  { code: "en", name: "English" },
  { code: "fr", name: "Français" },
  { code: "rw", name: "Kinyarwanda" },
];

// A language code, not an unrendered Jinja expression. `vite dev` serves
// index.html without running the template, so every bootstrap value below has
// to survive arriving as literal "{{ ... }}" text.
const LANG_CODE = /^[a-z]{2}(-[A-Za-z]+)?$/;

function cookieLang(): string | null {
  const cookie = document.cookie
    .split("; ")
    .find((c) => c.startsWith("preferred_language="));
  return cookie ? cookie.split("=")[1] : null;
}

// What the server decided, from <html lang>. egrm/www/grm-portal.py resolves it
// with Frappe's own get_language(), so it already accounts for the cookie, the
// Accept-Language header, the user record and System Settings.
function serverLang(): string | null {
  const lang = document.documentElement.lang;
  return LANG_CODE.test(lang) ? lang : null;
}

// The portal's own strings, inlined into the page by the same controller.
// Having them before the first render is the whole point: the alternative is
// rendering every label in English, fetching 82 KB, and re-rendering -- a
// flash of the wrong language, and a layout shift when the Kinyarwanda text
// turns out longer than the English it replaces.
function bootstrapMessages(): Translations | null {
  const el = document.getElementById("portal-i18n");
  if (!el?.textContent) return null;
  try {
    const parsed = JSON.parse(el.textContent);
    return parsed && typeof parsed === "object" ? (parsed as Translations) : null;
  } catch {
    return null;
  }
}

function initialLang(): string {
  // An explicit choice outranks inference. The cookie is checked first here
  // for the same reason the server checks it first for guests, and because a
  // signed-in officer who switched language should stay switched even though
  // get_language() would prefer their User record.
  return (
    cookieLang() ||
    serverLang() ||
    navigator.language?.split("-")[0] ||
    "en"
  );
}

// Seed the shared cache from the page so the first render is already
// translated. Marked partial below -- the fetch still runs, in the background,
// to fill in everything the inlined subset cannot carry.
const BOOTSTRAP_LANG = serverLang();
const BOOTSTRAP_MESSAGES = bootstrapMessages();
if (BOOTSTRAP_LANG && BOOTSTRAP_MESSAGES) {
  translationCache[BOOTSTRAP_LANG] = BOOTSTRAP_MESSAGES;
  partialLangs.add(BOOTSTRAP_LANG);
}

export const TranslateContext = createContext<TranslateContextValue>({
  __: (key) => key,
  lang: "en",
  setLang: () => {},
  languages: [],
  isLoading: false,
});

export function useTranslateProvider() {
  const { call } = useContext(FrappeContext) as FrappeConfig;
  const [lang, setLang] = useState(initialLang);
  // Not {} -- see bootstrapMessages(). When the page shipped the dictionary
  // for the language we are opening in, the very first render is translated.
  const [messages, setMessages] = useState<Translations>(
    () => translationCache[initialLang()] || {}
  );
  // Seeded, not empty. On a cold load get_all_languages has not answered
  // yet, and an empty list rendered the Navbar's language <select> with no
  // <option> at all -- a blank control, showing nothing, for the whole
  // round trip, on the one page element a citizen who cannot read the
  // default language has to find first. The seed is the same set the
  // backend enables, so in the normal case the options never change; when
  // the real list arrives it replaces this wholesale.
  const [languages, setLanguages] = useState<LanguageOption[]>(
    languagesCache || FALLBACK_LANGUAGES
  );
  // Whether `languages` is the server's answer rather than the seed above.
  // The correction effect below must not act on a guess.
  const [languagesResolved, setLanguagesResolved] = useState(!!languagesCache);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch the server-side preferred language ONCE on mount. If the user
  // has no cookie yet, adopt whatever the server suggests (user >
  // project > system) so the SPA opens in the project's language
  // out-of-the-box. Skipped if a cookie is already set — explicit user
  // choice always wins.
  useEffect(() => {
    if (cookieLang()) return;
    // The server already answered, in <html lang>, before this page parsed.
    if (serverLang()) return;
    call
      .get<{ message: { language: string; source: string } }>(
        "egrm.api.public_translations.get_preferred_language",
        {}
      )
      .then((data) => {
        const serverLang = data?.message?.language;
        if (serverLang && serverLang !== lang) {
          setLang(serverLang);
        }
      })
      .catch(() => {
        // Silent fallback — keep whatever the browser-locale init gave us.
      });
  }, []);

  // Fetch available languages from Frappe
  useEffect(() => {
    if (languagesCache) {
      setLanguages(languagesCache);
      setLanguagesResolved(true);
      return;
    }

    call
      .get<{ message: { language_code: string; language_name: string }[] }>(
        "frappe.translate.get_all_languages",
        { with_language_name: 1 }
      )
      .then((data) => {
        const langs: LanguageOption[] = (data?.message || []).map((l) => ({
          code: l.language_code,
          name: l.language_name,
        }));
        langs.sort((a, b) => a.name.localeCompare(b.name));
        languagesCache = langs;
        setLanguages(langs);
        setLanguagesResolved(true);
      })
      .catch(() => {
        // Deliberately NOT written to languagesCache: a transient failure
        // would otherwise pin the fallback for the whole session and the
        // backend list would never be picked up again.
        setLanguages(FALLBACK_LANGUAGES);
        setLanguagesResolved(true);
      });
  }, []);

  // Keep the selected language inside the set the backend actually offers.
  // `lang` is seeded from the browser locale, which is routinely something
  // eGRM has no translations for (de, sw, …). Left unchecked it would request
  // translations for a disabled language and leave the Navbar's <select> with
  // no matching <option>. No cookie is written — this is an inferred
  // correction, not an explicit user choice.
  useEffect(() => {
    // Only against the real list. Snapping the language on the strength of
    // the seed would move a citizen whose locale the backend does support
    // off it, before the request that proves it had even returned.
    if (!languagesResolved) return;
    if (!languages.length) return;
    if (languages.some((l) => l.code === lang)) return;
    const supported = languages.some((l) => l.code === "en")
      ? "en"
      : languages[0].code;
    setLang(supported);
  }, [languages, languagesResolved, lang]);

  // Fetch translations when language changes
  useEffect(() => {
    if (lang === "en") {
      setMessages({});
      return;
    }

    const cached = translationCache[lang];
    const complete = cached && !partialLangs.has(lang);
    if (complete) {
      setMessages(cached);
      return;
    }

    // Render whatever the page inlined while the rest is in flight, so the
    // first paint is already in the citizen's language.
    if (cached) setMessages(cached);
    // Nothing to render from is the only case worth announcing; a background
    // top-up behind a translated page is not a loading state.
    else setIsLoading(true);

    call
      .get<{ message: Translations }>(
        "egrm.api.public_translations.get_translations",
        { lang }
      )
      .then((data) => {
        const msgs = data?.message || {};
        // The inlined subset first: it came from the same source and the
        // fetched dictionary supersedes it key for key, but keeping it means a
        // partial failure can only ever lose keys it already had.
        const merged = { ...(cached || {}), ...msgs };
        translationCache[lang] = merged;
        partialLangs.delete(lang);
        setMessages(merged);
      })
      // Keep the subset on failure rather than falling back to English.
      .catch(() => setMessages(cached || {}))
      .finally(() => setIsLoading(false));
  }, [lang, call]);

  const __ = useCallback(
    (key: string, replacements?: string[]) => {
      let translated = messages[key] || key;
      if (replacements) {
        replacements.forEach((val, i) => {
          translated = translated.replace(`{${i}}`, val);
        });
      }
      return translated;
    },
    [messages]
  );

  const handleSetLang = useCallback((newLang: string) => {
    document.cookie = `preferred_language=${newLang};path=/;max-age=31536000`;
    setLang(newLang);
  }, []);

  return { __, lang, setLang: handleSetLang, languages, isLoading };
}

export function useTranslate() {
  return useContext(TranslateContext);
}
