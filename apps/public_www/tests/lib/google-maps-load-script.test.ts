import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

function installGoogleMapsStub(options?: {
  readonly includeMap?: boolean;
  readonly importLibrary?: (name: string) => Promise<unknown>;
}): void {
  const includeMap = options?.includeMap ?? true;
  window.google = {
    maps: {
      ...(includeMap
        ? {
            Map: class {
              constructor() {}
            },
          }
        : {}),
      importLibrary:
        options?.importLibrary ??
        vi.fn().mockResolvedValue({}),
    } as unknown as typeof google.maps,
  };
}

describe('loadGoogleMapsScript', () => {
  beforeEach(() => {
    vi.resetModules();
    document.getElementById('siutindei-google-maps-script')?.remove();
    Reflect.deleteProperty(window, 'google');
  });

  afterEach(() => {
    document.getElementById('siutindei-google-maps-script')?.remove();
    Reflect.deleteProperty(window, 'google');
  });

  it('returns immediately when Map is already available', async () => {
    const { loadGoogleMapsScript } = await import(
      '@/lib/google-maps/load-script'
    );
    installGoogleMapsStub();

    await expect(loadGoogleMapsScript('test-key')).resolves.toBeUndefined();
    expect(document.getElementById('siutindei-google-maps-script')).toBeNull();
  });

  it('waits for importLibrary before treating the script as ready', async () => {
    const { loadGoogleMapsScript } = await import(
      '@/lib/google-maps/load-script'
    );
    let resolveImport: ((value: unknown) => void) | undefined;
    const importLibrary = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveImport = resolve;
        }),
    );

    const load = loadGoogleMapsScript('test-key');
    const script = document.getElementById(
      'siutindei-google-maps-script',
    ) as HTMLScriptElement | null;
    expect(script).not.toBeNull();
    expect(script?.src).toContain('loading=async');
    expect(script?.src).toContain('callback=siutindeiMapsReady');

    installGoogleMapsStub({ includeMap: false, importLibrary });
    (window as Window & { siutindeiMapsReady?: () => void }).siutindeiMapsReady?.();

    await vi.waitFor(() => {
      expect(importLibrary).toHaveBeenCalledWith('maps');
    });

    let settled = false;
    void load.then(() => {
      settled = true;
    });
    expect(settled).toBe(false);

    installGoogleMapsStub({ importLibrary });
    resolveImport?.({});
    await expect(load).resolves.toBeUndefined();
    expect(settled).toBe(true);
  });

  it('waits when the script tag fires load before google.maps exists', async () => {
    const { loadGoogleMapsScript } = await import(
      '@/lib/google-maps/load-script'
    );
    let resolveImport: ((value: unknown) => void) | undefined;
    const importLibrary = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveImport = resolve;
        }),
    );

    const load = loadGoogleMapsScript('test-key');
    const script = document.getElementById(
      'siutindei-google-maps-script',
    ) as HTMLScriptElement | null;
    script?.dispatchEvent(new Event('load'));

    let settled = false;
    void load.then(() => {
      settled = true;
    });
    await new Promise((resolve) => {
      window.setTimeout(resolve, 80);
    });
    expect(settled).toBe(false);

    installGoogleMapsStub({ includeMap: false, importLibrary });
    (window as Window & { siutindeiMapsReady?: () => void }).siutindeiMapsReady?.();
    await vi.waitFor(() => {
      expect(importLibrary).toHaveBeenCalledWith('maps');
    });

    installGoogleMapsStub({ importLibrary });
    resolveImport?.({});
    await expect(load).resolves.toBeUndefined();
  });

  it('does not hang when a previous script tag already finished loading', async () => {
    const existing = document.createElement('script');
    existing.id = 'siutindei-google-maps-script';
    document.head.appendChild(existing);

    const { loadGoogleMapsScript } = await import(
      '@/lib/google-maps/load-script'
    );
    const load = loadGoogleMapsScript('test-key');

    await new Promise((resolve) => {
      window.setTimeout(resolve, 30);
    });
    installGoogleMapsStub();
    existing.dispatchEvent(new Event('load'));
    await expect(load).resolves.toBeUndefined();
  });
});
