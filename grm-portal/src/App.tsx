import { useLayoutEffect } from "react";
import { RouterProvider } from "react-router-dom";
import router from "./router";
import "./index.css";
import { FrappeProvider } from "frappe-react-sdk";
import { TranslateContext, useTranslateProvider } from "./hooks/useTranslate";

function TranslateBoundary({ children }: { children: React.ReactNode }) {
  const translate = useTranslateProvider();
  return (
    <TranslateContext.Provider value={translate}>{children}</TranslateContext.Provider>
  );
}

function App() {
  // @ts-expect-error frappe global
  const getSiteName = () => window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME;

  // Take down the boot shell from index.html now that there is something real
  // to replace it with. Doing it here, after the first commit, rather than
  // relying on createRoot to clear its container: the shell is a sibling of
  // #root precisely so the handoff is ours to time and does not depend on a
  // React implementation detail.
  useLayoutEffect(() => {
    document.getElementById("boot")?.remove();
  }, []);

  return (
    <FrappeProvider
      url={import.meta.env.VITE_FRAPPE_PATH ?? ""}
      socketPort={import.meta.env.VITE_SOCKET_PORT ? import.meta.env.VITE_SOCKET_PORT : undefined}
      siteName={getSiteName()}
    >
      <TranslateBoundary>
        <RouterProvider router={router} />
      </TranslateBoundary>
    </FrappeProvider>
  );
}

export default App;
