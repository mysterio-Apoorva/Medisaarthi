'use client';

import { useSyncExternalStore } from 'react';

export const STORAGE_UNAVAILABLE = '__storage_unavailable__';

function subscribe(listener: () => void) {
  window.addEventListener('storage', listener);
  return () => window.removeEventListener('storage', listener);
}

/** UI preferences only; clinical records always come from the API. */
export function useStoredPreference(key: string) {
  return useSyncExternalStore(subscribe, () => {
    try { return localStorage.getItem(key); }
    catch { return STORAGE_UNAVAILABLE; }
  }, () => null);
}
