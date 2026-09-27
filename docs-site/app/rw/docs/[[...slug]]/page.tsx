import { sourceRw } from '@/lib/source';
import {
  DocsBody,
  DocsDescription,
  DocsPage,
  DocsTitle,
} from 'fumadocs-ui/layouts/docs/page';
import { notFound } from 'next/navigation';
import { getMDXComponents } from '@/components/mdx';
import type { Metadata } from 'next';
import { createRelativeLink } from 'fumadocs-ui/mdx';
import { appNameRw } from '@/lib/shared';

export default async function Page(props: PageProps<'/rw/docs/[[...slug]]'>) {
  const params = await props.params;
  const page = sourceRw.getPage(params.slug);
  if (!page) notFound();

  const MDX = page.data.body;

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription className="mb-6 border-b pb-6">{page.data.description}</DocsDescription>
      <DocsBody>
        <MDX
          components={getMDXComponents({
            a: createRelativeLink(sourceRw, page),
          })}
        />
      </DocsBody>
    </DocsPage>
  );
}

export async function generateStaticParams() {
  return sourceRw.generateParams();
}

export async function generateMetadata(props: PageProps<'/rw/docs/[[...slug]]'>): Promise<Metadata> {
  const params = await props.params;
  const page = sourceRw.getPage(params.slug);
  if (!page) notFound();

  return {
    // Absolute, so the root layout's English `%s · eGRM User Guide` template
    // does not put an English product name in a Kinyarwanda browser tab.
    title: { absolute: `${page.data.title} · ${appNameRw}` },
    description: page.data.description,
  };
}
