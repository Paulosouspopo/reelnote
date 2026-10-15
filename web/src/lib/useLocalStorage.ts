"use client";

import { useCallback, useSyncExternalStore } from "react";

const EVENT = "reelnote:local-storage";

function subscribe(onChange: () => void) {
  window.addEventListener("storage", onChange);
  window.addEventListener(EVENT, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(EVENT, onChange);
  };
}

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // navigation privée, stockage bloqué…
  }
}

/**
 * Valeur brute stockée sur l'appareil, sans incohérence d'hydratation
 * (le serveur rend toujours `null`). Réservé aux petits conforts locaux :
 * rien d'important ne doit dépendre du stockage du navigateur.
 */
export function useLocalStorage(key: string): [string | null, (value: string | null) => void] {
  const value = useSyncExternalStore(
    subscribe,
    () => read(key),
    () => null,
  );

  const write = useCallback(
    (next: string | null) => {
      try {
        if (next === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, next);
      } catch {
        // ignoré : simple confort
      }
      window.dispatchEvent(new Event(EVENT));
    },
    [key],
  );

  return [value, write];
}
