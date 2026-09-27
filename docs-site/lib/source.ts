import { llms, loader } from 'fumadocs-core/source';
import { docsRoute, docsRouteRw } from './shared';
import { defineDocs } from 'fumadocs-mdx/macro';
import { metaSchema, pageSchema } from 'fumadocs-core/source/schema';

const docs = defineDocs({
  dir: 'content/docs',
  docs: {
    schema: pageSchema,
    postprocess: {
      includeProcessedMarkdown: true,
    },
  },
  meta: {
    schema: metaSchema,
  },
});

const docsRw = defineDocs({
  dir: 'content/docs-rw',
  docs: {
    schema: pageSchema,
    postprocess: {
      includeProcessedMarkdown: true,
    },
  },
  meta: {
    schema: metaSchema,
  },
});

// See https://fumadocs.dev/docs/headless/source-api for more info
export const source = loader({
  baseUrl: docsRoute,
  source: docs.toFumadocsSource(),
  plugins: [],
});

// The Kinyarwanda tree mirrors the English one file for file. `content/docs-rw/img`
// is a symlink to the English `img` directory, so every `../img/...` path in a
// translated page resolves to the same screenshot without being rewritten.
export const sourceRw = loader({
  baseUrl: docsRouteRw,
  source: docsRw.toFumadocsSource(),
  plugins: [],
});

export const docsLlms = llms(source, {
  renderPage: async (page) => `# ${page.data.title} (${page.url})

${await page.data.getText('processed')}`,
});
