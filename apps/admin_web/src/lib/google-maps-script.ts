'use client';

const SCRIPT_ID = 'admin-google-maps-script';
const BOOTSTRAP_POLL_MS = 50;
const BOOTSTRAP_TIMEOUT_MS = 10_000;
let loadPromise: Promise<void> | null = null;

function hasMapsConstructor(): boolean {
  return typeof window.google?.maps?.Map === 'function';
}

function getImportLibrary():
  | ((name: string) => Promise<unknown>)
  | undefined {
  const importLibrary = window.google?.maps?.importLibrary;
  return typeof importLibrary === 'function' ? importLibrary : undefined;
}

function waitForMapsBootstrap(): Promise<void> {
  if (hasMapsConstructor() || getImportLibrary()) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    const startedAt = Date.now();
    const intervalId = window.setInterval(() => {
      if (hasMapsConstructor() || getImportLibrary()) {
        window.clearInterval(intervalId);
        resolve();
        return;
      }
      if (Date.now() - startedAt >= BOOTSTRAP_TIMEOUT_MS) {
        window.clearInterval(intervalId);
        reject(new Error('Google Maps failed to load.'));
      }
    }, BOOTSTRAP_POLL_MS);
  });
}

function ensureScriptTag(apiKey: string, onError: () => void): void {
  if (document.getElementById(SCRIPT_ID)) {
    return;
  }

  const script = document.createElement('script');
  script.id = SCRIPT_ID;
  script.async = true;
  script.src =
    `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}` +
    '&loading=async';
  script.onerror = onError;
  document.head.appendChild(script);
}

async function loadMapsLibraries(): Promise<void> {
  await waitForMapsBootstrap();
  const importLibrary = getImportLibrary();
  if (importLibrary && !hasMapsConstructor()) {
    await importLibrary('maps');
  }
  if (importLibrary) {
    await importLibrary('marker');
  }
  if (!hasMapsConstructor()) {
    throw new Error('Google Maps failed to load.');
  }
}

export async function loadGoogleMapsScript(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') {
    throw new Error('Google Maps requires a browser.');
  }

  if (hasMapsConstructor()) {
    return;
  }

  if (!loadPromise) {
    loadPromise = new Promise<void>((resolve, reject) => {
      ensureScriptTag(apiKey, () => {
        reject(new Error('Google Maps failed to load.'));
      });
      void waitForMapsBootstrap().then(resolve).catch(reject);
    })
      .then(() => loadMapsLibraries())
      .catch((error: unknown) => {
        loadPromise = null;
        return Promise.reject(error);
      });
  }

  await loadPromise;
}
