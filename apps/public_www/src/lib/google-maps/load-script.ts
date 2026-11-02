'use client';

const SCRIPT_ID = 'siutindei-google-maps-script';
const MAPS_CALLBACK = 'siutindeiMapsReady';
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

function mapsReady(): boolean {
  return hasMapsConstructor() || Boolean(getImportLibrary());
}

function waitForMapsBootstrap(script: HTMLScriptElement): Promise<void> {
  if (mapsReady()) {
    return Promise.resolve();
  }

  return new Promise<void>((resolve, reject) => {
    let settled = false;
    const timeoutId = window.setTimeout(() => {
      if (settled) {
        return;
      }
      settled = true;
      reject(new Error('Google Maps failed to load.'));
    }, BOOTSTRAP_TIMEOUT_MS);

    const finish = () => {
      if (settled || !mapsReady()) {
        return;
      }
      settled = true;
      window.clearTimeout(timeoutId);
      resolve();
    };

    const callbackWindow = window as Window & { [MAPS_CALLBACK]?: () => void };
    const previous = callbackWindow[MAPS_CALLBACK];
    callbackWindow[MAPS_CALLBACK] = () => {
      previous?.();
      finish();
    };
    script.addEventListener('load', finish, { once: true });
    script.addEventListener(
      'error',
      () => {
        if (settled) {
          return;
        }
        settled = true;
        window.clearTimeout(timeoutId);
        reject(new Error('Google Maps failed to load.'));
      },
      { once: true },
    );
  });
}

function ensureScriptTag(apiKey: string): HTMLScriptElement {
  const existing = document.getElementById(SCRIPT_ID);
  if (existing instanceof HTMLScriptElement) {
    return existing;
  }

  const script = document.createElement('script');
  script.id = SCRIPT_ID;
  script.async = true;
  script.src =
    `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}` +
    `&loading=async&callback=${MAPS_CALLBACK}`;
  document.head.appendChild(script);
  return script;
}

async function loadMapsLibraries(): Promise<void> {
  const importLibrary = getImportLibrary();
  if (importLibrary && !hasMapsConstructor()) {
    await importLibrary('maps');
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
    const script = ensureScriptTag(apiKey);
    loadPromise = waitForMapsBootstrap(script)
      .then(() => loadMapsLibraries())
      .catch((error: unknown) => {
        loadPromise = null;
        return Promise.reject(error);
      });
  }

  await loadPromise;
}
