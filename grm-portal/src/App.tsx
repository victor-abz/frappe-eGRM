import { RouterProvider } from "react-router-dom";
import router from "./router";
import "./index.css";
import { FrappeProvider } from "frappe-react-sdk";
import { TranslateContext, useTranslateProvider } from "./hooks/useTranslate";

function App() {
  // @ts-expect-error frappe global
  const getSiteName = () => window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME;
  const translate = useTranslateProvider();

  return (
    <FrappeProvider
      url={import.meta.env.VITE_FRAPPE_PATH ?? ""}
      socketPort={import.meta.env.VITE_SOCKET_PORT ? import.meta.env.VITE_SOCKET_PORT : undefined}
      siteName={getSiteName()}
    >
      <TranslateContext.Provider value={translate}>
        <RouterProvider router={router} />
      </TranslateContext.Provider>
    </FrappeProvider>
  );
}

export default App;
