'use client';

import { useEffect } from 'react';

/**
 * The root layout is shared by both guides and hardcodes `lang="en"`, which a
 * nested layout cannot override. This corrects it for the Kinyarwanda tree so
 * screen readers and browser translation treat the page as Kinyarwanda.
 */
export function HtmlLang({ lang }: { lang: string }) {
  useEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = lang;
    return () => {
      document.documentElement.lang = previous;
    };
  }, [lang]);

  return null;
}
