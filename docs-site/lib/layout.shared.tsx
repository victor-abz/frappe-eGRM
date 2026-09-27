import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { LanguageToggle } from '@/components/language-toggle';
import { appName, appNameRw } from './shared';

export type GuideLocale = 'en' | 'rw';

export function baseOptions(locale: GuideLocale = 'en'): BaseLayoutProps {
  return {
    nav: {
      title: locale === 'rw' ? appNameRw : appName,
      url: locale === 'rw' ? '/rw' : '/',
    },
    links: [{ type: 'custom', secondary: true, children: <LanguageToggle /> }],
    // Deliberately no githubUrl: this guide ships inside the eGRM app and is
    // read by citizens and government staff, not by people with repo access.
  };
}
