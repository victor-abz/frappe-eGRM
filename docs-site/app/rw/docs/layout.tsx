import { sourceRw } from '@/lib/source';
import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { baseOptions } from '@/lib/layout.shared';
import { HtmlLang } from '@/components/html-lang';

export default function Layout({ children }: LayoutProps<'/rw/docs'>) {
  return (
    <DocsLayout tree={sourceRw.getPageTree()} {...baseOptions('rw')}>
      <HtmlLang lang="rw" />
      {children}
    </DocsLayout>
  );
}
