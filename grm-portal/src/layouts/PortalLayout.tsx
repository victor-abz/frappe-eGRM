import { useEffect, useRef } from "react";
import { Outlet, useLocation, useMatches } from "react-router-dom";
import Navbar from "@/components/Navbar";
import { useTranslate } from "@/hooks/useTranslate";

interface RouteHandle {
  title?: string;
}

export default function PortalLayout() {
  const { __, lang } = useTranslate();
  const { pathname } = useLocation();
  const matches = useMatches();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  // A single-page app changes the document without telling assistive
  // technology, so a screen-reader user who follows a nav link stays
  // announced on the old page. Moving focus to <main> on each navigation
  // is what a full page load would have done for free.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [pathname]);

  // Keep the document language honest so screen readers switch voice and
  // the browser offers the right spellcheck and translation.
  useEffect(() => {
    document.documentElement.lang = lang || "en";
  }, [lang]);

  // Every route shared one title, so browser history, a row of open tabs and
  // the first thing a screen reader reads on arrival were identical on all
  // six pages. The title comes from the route's own handle and is translated
  // here, which is why this re-runs when the language changes.
  useEffect(() => {
    const titled = [...matches]
      .reverse()
      .find((m) => (m.handle as RouteHandle | undefined)?.title);
    const page = (titled?.handle as RouteHandle | undefined)?.title;
    const site = __("GRM Public Portal");
    document.title = page ? `${__(page)} — ${site}` : site;
  }, [matches, lang, __]);

  return (
    <div className="flex min-h-screen flex-col bg-white">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-primary-800 focus:px-4 focus:py-3 focus:font-semibold focus:text-white"
      >
        {__("Skip to main content")}
      </a>
      <Navbar />
      <main
        id="main-content"
        ref={mainRef}
        tabIndex={-1}
        className="flex-1 focus:outline-none"
      >
        <Outlet />
      </main>
      <footer className="border-t border-grm-border py-6 text-center text-sm text-grm-secondary">
        {__("Grievance Redress Mechanism")} &mdash; {__("Public Portal")}
      </footer>
    </div>
  );
}
