import { vi } from 'vitest';

import '@testing-library/jest-dom/vitest';

// Node 26 exposes a localStorage global that is empty unless
// --localstorage-file is set. jsdom then leaves window.localStorage unset.
function memoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear() {
      values.clear();
    },
    getItem(key: string) {
      return values.get(key) ?? null;
    },
    key(index: number) {
      return [...values.keys()][index] ?? null;
    },
    removeItem(key: string) {
      values.delete(key);
    },
    setItem(key: string, value: string) {
      values.set(key, String(value));
    },
  };
}

function readStorage(name: 'localStorage' | 'sessionStorage'): Storage | undefined {
  try {
    return window[name];
  } catch {
    return undefined;
  }
}

function installStorage(name: 'localStorage' | 'sessionStorage') {
  const current = readStorage(name);
  if (current != null && typeof current.clear === 'function') {
    return;
  }
  const storage = memoryStorage();
  vi.stubGlobal(name, storage);
  try {
    Object.defineProperty(window, name, {
      configurable: true,
      value: storage,
    });
  } catch {
    // The Node global is not configurable. stubGlobal still replaces it.
  }
}

if (typeof window !== 'undefined') {
  installStorage('localStorage');
  installStorage('sessionStorage');
}

process.env.NEXT_PUBLIC_SITE_ORIGIN ??= 'http://localhost:3000';
process.env.NEXT_PUBLIC_SITE_NAME ??= 'Siu Tin Dei';
process.env.NEXT_PUBLIC_SITE_TAGLINE ??=
  "Curated children's activities in Hong Kong.";
