var __assign = (this && this.__assign) || function () {
    __assign = Object.assign || function(t) {
        for (var s, i = 1, n = arguments.length; i < n; i++) {
            s = arguments[i];
            for (var p in s) if (Object.prototype.hasOwnProperty.call(s, p))
                t[p] = s[p];
        }
        return t;
    };
    return __assign.apply(this, arguments);
};
var __spreadArray = (this && this.__spreadArray) || function (to, from, pack) {
    if (pack || arguments.length === 2) for (var i = 0, l = from.length, ar; i < l; i++) {
        if (ar || !(i in from)) {
            if (!ar) ar = Array.prototype.slice.call(from, 0, i);
            ar[i] = from[i];
        }
    }
    return to.concat(ar || Array.prototype.slice.call(from));
};
import "dotenv/config";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import react from "@vitejs/plugin-react";
import checker from "vite-plugin-checker";
import { defineConfig } from "vitest/config";
var gaMeasurementId = process.env.VITE_GA_MEASUREMENT_ID || process.env.GA_MEASUREMENT_ID || "";
var googleClientId = process.env.VITE_GOOGLE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID || "";
export default defineConfig({
    plugins: __spreadArray([
        {
            name: "inject-google-analytics",
            transformIndexHtml: function () {
                if (!gaMeasurementId) {
                    return [];
                }
                return [
                    {
                        tag: "script",
                        attrs: {
                            async: true,
                            src: "https://www.googletagmanager.com/gtag/js?id=".concat(encodeURIComponent(gaMeasurementId)),
                        },
                        injectTo: "head",
                    },
                    {
                        tag: "script",
                        children: [
                            "window.dataLayer = window.dataLayer || [];",
                            "function gtag(){dataLayer.push(arguments);}",
                            "gtag('js', new Date());",
                            "gtag('config', ".concat(JSON.stringify(gaMeasurementId), ", { send_page_view: false });"),
                        ].join("\n"),
                        injectTo: "head",
                    },
                ];
            },
        },
        react(),
        checker({
            typescript: true,
        })
    ], (process.env.SENTRY_AUTH_TOKEN
        ? [
            sentryVitePlugin(__assign(__assign({ org: process.env.SENTRY_ORG, project: process.env.SENTRY_PROJECT, authToken: process.env.SENTRY_AUTH_TOKEN }, (process.env.SENTRY_RELEASE
                ? { release: { name: process.env.SENTRY_RELEASE } }
                : {})), { sourcemaps: { assets: "./dist/**" }, telemetry: false })),
        ]
        : []), true),
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
    define: __assign(__assign({ "import.meta.env.VITE_GA_MEASUREMENT_ID": JSON.stringify(gaMeasurementId) }, (googleClientId
        ? {
            "import.meta.env.VITE_GOOGLE_CLIENT_ID": JSON.stringify(googleClientId),
        }
        : {})), { "import.meta.env.VITE_SENTRY_DSN": JSON.stringify(process.env.VITE_SENTRY_DSN || process.env.SENTRY_DSN || ""), "import.meta.env.VITE_SENTRY_RELEASE": JSON.stringify(process.env.VITE_SENTRY_RELEASE || process.env.SENTRY_RELEASE || "") }),
});
