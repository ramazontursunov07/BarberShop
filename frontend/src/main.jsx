import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { AuthProvider } from "./auth.jsx";
import { I18nProvider } from "./i18n.jsx";
import { initTelegram } from "./telegram.js";
import { ToastProvider } from "./components/Toast.jsx";
import { applyTheme, getTheme } from "./theme.js";
import "./styles.css";

applyTheme(getTheme());

initTelegram();

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <I18nProvider>
        <AuthProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </AuthProvider>
      </I18nProvider>
    </BrowserRouter>
  </React.StrictMode>
);
