import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { initializeGoogleAnalytics } from "./analytics";
import { AppProviders } from "./AppProviders";
import "./index.css";
import { RootRoutes } from "./routes/RootRoutes";

initializeGoogleAnalytics();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProviders>
      <RootRoutes />
    </AppProviders>
  </StrictMode>,
);
