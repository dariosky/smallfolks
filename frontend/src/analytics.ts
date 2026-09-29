const GA_MEASUREMENT_ID = import.meta.env.VITE_GA_MEASUREMENT_ID;

type AnalyticsWindow = Window &
  typeof globalThis & {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
  };

function getAnalyticsWindow(): AnalyticsWindow {
  return window as AnalyticsWindow;
}

export function initializeGoogleAnalytics() {
  if (!GA_MEASUREMENT_ID || typeof window === "undefined") {
    return;
  }
  const analyticsWindow = getAnalyticsWindow();
  analyticsWindow.dataLayer = analyticsWindow.dataLayer ?? [];
  analyticsWindow.gtag =
    analyticsWindow.gtag ??
    function gtag(...args: unknown[]) {
      analyticsWindow.dataLayer?.push(args);
    };
  analyticsWindow.gtag("js", new Date());
  analyticsWindow.gtag("config", GA_MEASUREMENT_ID, { send_page_view: false });
}

export function trackPageView(path: string, title: string = document.title) {
  const analyticsWindow = getAnalyticsWindow();
  if (!GA_MEASUREMENT_ID || !analyticsWindow.gtag) {
    return;
  }
  analyticsWindow.gtag("event", "page_view", {
    page_location: analyticsWindow.location.href,
    page_path: path,
    page_title: title,
  });
}
