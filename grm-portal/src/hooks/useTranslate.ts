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

export const TranslateContext = createContext<TranslateContextValue>({
  __: (key) => key,
  lang: "en",
  setLang: () => {},
  languages: [],
  isLoading: false,
});

export function useTranslateProvider() {
  const { call } = useContext(FrappeContext) as FrappeConfig;
  const [lang, setLang] = useState(() => {
    // Priority: cookie > browser > "en". Server-derived default
    // (logged-in user / project / system) is fetched async below and
    // applied if no cookie is set yet.
    const cookie = document.cookie
      .split("; ")
      .find((c) => c.startsWith("preferred_language="));
    if (cookie) return cookie.split("=")[1];
    return navigator.language?.split("-")[0] || "en";
  });
  const [messages, setMessages] = useState<Translations>({});
  const [languages, setLanguages] = useState<LanguageOption[]>(languagesCache || []);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch the server-side preferred language ONCE on mount. If the user
  // has no cookie yet, adopt whatever the server suggests (user >
  // project > system) so the SPA opens in the project's language
  // out-of-the-box. Skipped if a cookie is already set — explicit user
  // choice always wins.
  useEffect(() => {
    const hasCookie = document.cookie
      .split("; ")
      .some((c) => c.startsWith("preferred_language="));
    if (hasCookie) return;
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
      })
      .catch(() => {
        // Deliberately NOT written to languagesCache: a transient failure
        // would otherwise pin the fallback for the whole session and the
        // backend list would never be picked up again.
        setLanguages(FALLBACK_LANGUAGES);
      });
  }, []);

  // Keep the selected language inside the set the backend actually offers.
  // `lang` is seeded from the browser locale, which is routinely something
  // eGRM has no translations for (de, sw, …). Left unchecked it would request
  // translations for a disabled language and leave the Navbar's <select> with
  // no matching <option>. No cookie is written — this is an inferred
  // correction, not an explicit user choice.
  useEffect(() => {
    if (!languages.length) return;
    if (languages.some((l) => l.code === lang)) return;
    const supported = languages.some((l) => l.code === "en")
      ? "en"
      : languages[0].code;
    setLang(supported);
  }, [languages, lang]);

  // Fetch translations when language changes
  useEffect(() => {
    if (lang === "en") {
      setMessages({});
      return;
    }

    if (translationCache[lang]) {
      setMessages(translationCache[lang]);
      return;
    }

    setIsLoading(true);
    call
      .get<{ message: Translations }>(
        "egrm.api.public_translations.get_translations",
        { lang }
      )
      .then((data) => {
        const msgs = data?.message || {};
        translationCache[lang] = msgs;
        setMessages(msgs);
      })
      .catch(() => setMessages({}))
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
