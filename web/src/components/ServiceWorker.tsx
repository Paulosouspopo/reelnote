"use client";

import { useEffect } from "react";

/** Enregistre le service worker (notifications push + page hors ligne). */
export function ServiceWorker() {
  useEffect(() => {
    if (!("serviceWorker" in navigator) || process.env.NODE_ENV !== "production") return;
    navigator.serviceWorker.register("/sw.js", { scope: "/", updateViaCache: "none" }).catch((error: unknown) => {
      console.warn("Service worker non enregistré", error);
    });
  }, []);
  return null;
}
