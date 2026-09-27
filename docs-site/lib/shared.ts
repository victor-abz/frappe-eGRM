import { createGetUrl } from 'fumadocs-core/source';

export const appName = 'eGRM User Guide';
export const docsRoute = '/docs';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

// Kinyarwanda lives in a parallel route rather than behind fumadocs' i18n
// middleware: middleware cannot run under `output: "export"`, and keeping the
// English URLs exactly where they are means every existing bookmark and every
// link already sent to staff keeps working.
export const appNameRw = 'Gukoresha eGRM';
export const docsRouteRw = '/rw/docs';
export const homeRouteRw = '/rw';

const getContentUrl = createGetUrl(docsContentRoute);

export function getPageMarkdownUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'content.md'];

  return { segments, url: getContentUrl(segments, page.locale) };
}

const getImageUrl = createGetUrl(docsImageRoute);

export function getPageImageUrl(page: { slugs: string[]; locale?: string }) {
  const segments = [...page.slugs, 'image.png'];

  return { segments, url: getImageUrl(segments, page.locale) };
}
