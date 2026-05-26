import { createRoot } from "react-dom/client";

import "./globals.css";

import { App } from "./app/App";
import "./i18n";
import { initKea } from "./initKea";

initKea();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error('Missing <div id="root"> in index.html');
}

createRoot(rootElement).render(<App />);
