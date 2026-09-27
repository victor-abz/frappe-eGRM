import { HomeLayout } from 'fumadocs-ui/layouts/home';
import { baseOptions } from '@/lib/layout.shared';
import { HtmlLang } from '@/components/html-lang';

export default function Layout({ children }: LayoutProps<'/rw'>) {
  return (
    <HomeLayout {...baseOptions('rw')}>
      <HtmlLang lang="rw" />
      {children}
    </HomeLayout>
  );
}
