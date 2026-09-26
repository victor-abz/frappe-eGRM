import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';
import { appName } from './shared';

export function baseOptions(): BaseLayoutProps {
  return {
    nav: {
      title: appName,
    },
    // Deliberately no githubUrl: this guide ships inside the eGRM app and is
    // read by citizens and government staff, not by people with repo access.
  };
}
