'use client';

import { useEffect } from 'react';

/**
 * The root layout is shared by both guides and hardcodes `lang="en"`, which a
 * nested layout cannot override. This corrects it for the Kinyarwanda tree so
 * screen readers and browser translation treat the page as Kinyarwanda.
 *
 * The inline script runs while the browser is still parsing the document, so
 * the attribute is right before anything reads it; the effect keeps it right
 * across client-side navigation and puts it back on the way out.
 */
export function HtmlLang({ lang }: { lang: string }) {
  useEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = lang;
    return () => {
      document.documentElement.lang = previous;
    };
  }, [lang]);

  return (
    <script
      dangerouslySetInnerHTML={{
        __html: `document.documentElement.lang=${JSON.stringify(lang)}`,
      }}
    />
  );
}
