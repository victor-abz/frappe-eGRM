import { createContext, useContext, useState, useEffect, useCallback } from "react";

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

export const TranslateContext = createContext<TranslateContextValue>({
  __: (key) => key,
  lang: "en",
  setLang: () => {},
  languages: [],
  isLoading: false,
});

export function useTranslateProvider() {
  const [lang, setLang] = useState(() => {
    // Priority: cookie > browser > "en"
    const cookie = document.cookie
      .split("; ")
      .find((c) => c.startsWith("preferred_language="));
    if (cookie) return cookie.split("=")[1];
    return navigator.language?.split("-")[0] || "en";
  });
  const [messages, setMessages] = useState<Translations>({});
  const [languages, setLanguages] = useState<LanguageOption[]>(languagesCache || []);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch available languages from Frappe
  useEffect(() => {
    if (languagesCache) {
      setLanguages(languagesCache);
      return;
    }

    fetch('/api/method/frappe.translate.get_all_languages?with_language_name=True')
      .then((r) => r.json())
      .then((data) => {
        const langs: LanguageOption[] = (data.message || []).map((l: any) => ({
          code: l.language_code,
          name: l.language_name,
        }));
        langs.sort((a, b) => a.name.localeCompare(b.name));
        languagesCache = langs;
        setLanguages(langs);
      })
      .catch(() => {
        // Fallback if API fails
        const fallback = [
          { code: "en", name: "English" },
          { code: "fr", name: "Français" },
          { code: "rw", name: "Kinyarwanda" },
          { code: "sw", name: "Kiswahili" },
        ];
        languagesCache = fallback;
        setLanguages(fallback);
      });
  }, []);

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
    fetch(`/api/method/egrm.api.public_translations.get_translations?lang=${lang}`)
      .then((r) => r.json())
      .then((data) => {
        const msgs = data.message || {};
        translationCache[lang] = msgs;
        setMessages(msgs);
      })
      .catch(() => setMessages({}))
      .finally(() => setIsLoading(false));
  }, [lang]);

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
