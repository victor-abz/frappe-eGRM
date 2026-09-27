'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const RW_PREFIX = '/rw';

/**
 * Switches between the two parallel guides.
 *
 * It tries to land on the same page in the other language: `/docs/mobile/record`
 * becomes `/rw/docs/mobile/record` and back again. The trees mirror each other
 * file for file, so that mapping always has a target.
 */
export function LanguageToggle() {
  const pathname = usePathname() ?? '/';
  const isRw = pathname === RW_PREFIX || pathname.startsWith(`${RW_PREFIX}/`);

  const target = isRw ? pathname.slice(RW_PREFIX.length) || '/' : `${RW_PREFIX}${pathname}`;
  const label = isRw ? 'English' : 'Kinyarwanda';

  return (
    <Link
      href={target}
      hrefLang={isRw ? 'en' : 'rw'}
      className="text-sm font-medium text-fd-muted-foreground transition-colors hover:text-fd-foreground"
    >
      {label}
    </Link>
  );
}
