import "dotenv/config";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import react from "@vitejs/plugin-react";
import checker from "vite-plugin-checker";
import { defineConfig } from "vitest/config";

const gaMeasurementId =
  process.env.VITE_GA_MEASUREMENT_ID || process.env.GA_MEASUREMENT_ID || "";
const googleClientId =
  process.env.VITE_GOOGLE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID || "";

export default defineConfig({
  plugins: [
    {
      name: "inject-google-analytics",
      transformIndexHtml() {
        if (!gaMeasurementId) {
          return [];
        }
        return [
          {
            tag: "script",
            attrs: {
              async: true,
              src: `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gaMeasurementId)}`,
            },
            injectTo: "head",
          },
          {
            tag: "script",
            children: [
              "window.dataLayer = window.dataLayer || [];",
              "function gtag(){dataLayer.push(arguments);}",
              "gtag('js', new Date());",
              `gtag('config', ${JSON.stringify(gaMeasurementId)}, { send_page_view: false });`,
            ].join("\n"),
            injectTo: "head",
          },
        ];
      },
    },
    react(),
    checker({
      typescript: true,
    }),
    ...(process.env.SENTRY_AUTH_TOKEN
      ? [
          sentryVitePlugin({
            org: process.env.SENTRY_ORG,
            project: process.env.SENTRY_PROJECT,
            authToken: process.env.SENTRY_AUTH_TOKEN,
            ...(process.env.SENTRY_RELEASE
              ? { release: { name: process.env.SENTRY_RELEASE } }
              : {}),
            sourcemaps: { assets: "./dist/**" },
            telemetry: false,
          }),
        ]
      : []),
  ],
  server: {
    host: "127.0.0.1",
    port: 5341,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5340",
        changeOrigin: true,
      },
    },
    hmr: {
      host: "127.0.0.1",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
  define: {
    "import.meta.env.VITE_GA_MEASUREMENT_ID": JSON.stringify(gaMeasurementId),
    ...(googleClientId
      ? {
          "import.meta.env.VITE_GOOGLE_CLIENT_ID":
            JSON.stringify(googleClientId),
        }
      : {}),
    "import.meta.env.VITE_SENTRY_DSN": JSON.stringify(
      process.env.VITE_SENTRY_DSN || process.env.SENTRY_DSN || "",
    ),
    "import.meta.env.VITE_SENTRY_RELEASE": JSON.stringify(
      process.env.VITE_SENTRY_RELEASE || process.env.SENTRY_RELEASE || "",
    ),
  },
});
