import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { I18nProvider } from "./i18n";
import { ServiceProvider } from "./service";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("#root is missing from index.html");
}

createRoot(root).render(
  <StrictMode>
    <I18nProvider>
      <ServiceProvider>
        <App />
      </ServiceProvider>
    </I18nProvider>
  </StrictMode>,
);
