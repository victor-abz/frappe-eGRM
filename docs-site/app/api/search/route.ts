import { source, sourceRw } from '@/lib/source';
import { createSearchAPI } from 'fumadocs-core/search/server';

export const revalidate = false;

// One index covers both guides. The static client fetches a single file, and a
// reader who types a Kinyarwanda word finds the Kinyarwanda page even if they
// are currently on the English one — which is what people actually do here.
export const { staticGET: GET } = createSearchAPI('advanced', {
  // https://docs.orama.com/docs/orama-js/supported-languages — Kinyarwanda is
  // not among them; the English tokenizer splits on whitespace, which is
  // enough for the exact screen labels people search for.
  language: 'english',
  indexes: [...source.getPages(), ...sourceRw.getPages()].map((page) => ({
    id: page.url,
    url: page.url,
    title: page.data.title,
    description: page.data.description,
    structuredData: page.data.structuredData,
  })),
});
