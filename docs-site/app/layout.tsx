import { Inter } from 'next/font/google';
import { Provider } from '@/components/provider';
import type { Metadata } from 'next';
import './global.css';

// Without this the browser tab shows a bare URL, which is what people see
// first when they bookmark the guide or send it to a colleague.
export const metadata: Metadata = {
  title: {
    default: 'eGRM User Guide',
    template: '%s · eGRM User Guide',
  },
  description:
    'How to report a problem to the Grievance Redress Mechanism, and how staff record, assign and resolve it.',
};

const inter = Inter({
  subsets: ['latin'],
});

export default function Layout({ children }: LayoutProps<'/'>) {
  return (
    <html lang="en" className={inter.className} suppressHydrationWarning>
      <body className="flex flex-col min-h-screen">
        <Provider>{children}</Provider>
      </body>
    </html>
  );
}
