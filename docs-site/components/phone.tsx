import type { ReactNode } from 'react';

/**
 * Frames a phone screenshot. The app shots are 1080x2280 — left to the
 * prose column they render about 1500px tall and push all the surrounding
 * text off the screen. Capped to roughly life size; ImageZoom still opens
 * the full-resolution image on click.
 */
export function Phone({ children }: { children: ReactNode }) {
  return <div className="phone-shot">{children}</div>;
}
