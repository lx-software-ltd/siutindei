import { render, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ActivityGoogleMap } from '@/components/shared/maps/activity-google-map';
import type { ActivityListing } from '@/lib/activities/types';
import { iconSrcForActivity } from '@/lib/home-wizard/choice-icons';

const markerOptions: google.maps.MarkerOptions[] = [];
const mapConstructors: unknown[] = [];

vi.mock('@/lib/google-maps/config', () => ({
  getGoogleMapsConfig: () => ({ apiKey: 'test-key' }),
}));

vi.mock('@/lib/google-maps/load-script', () => ({
  loadGoogleMapsScript: vi.fn().mockResolvedValue(undefined),
}));

function buildListing(): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: 'c1111111-1111-1111-1111-111111111101',
    },
    organization: {
      id: 'org-1',
      name: 'Studio',
      description: null,
      nameTranslations: {},
      mediaUrls: [],
      logoMediaUrl: null,
    },
    location: {
      id: 'loc-1',
      areaId: 'a1111111-1111-1111-1111-111111111102',
      regionAreaId: 'a1111111-1111-1111-1111-111111111102',
      address: null,
      lat: 22.3193,
      lng: 114.1694,
    },
    pricing: {
      pricingType: 'per_class',
      amount: 180,
      currency: 'hkd',
      sessionsCount: null,
      freeTrialClassOffered: false,
    },
    schedule: {
      scheduleType: 'weekly',
      weeklyEntries: [],
      languages: ['en'],
    },
  };
}

function installGoogleMaps(): void {
  markerOptions.length = 0;
  mapConstructors.length = 0;
  window.google = {
    maps: {
      LatLng: class {
        constructor(
          readonly lat: number,
          readonly lng: number,
        ) {}
      },
      LatLngBounds: class {
        extend(): void {}
      },
      Size: class {
        constructor(
          readonly width: number,
          readonly height: number,
        ) {}
      },
      Point: class {
        constructor(
          readonly x: number,
          readonly y: number,
        ) {}
      },
      Map: class {
        constructor() {
          mapConstructors.push(this);
        }
        fitBounds(): void {}
        panTo(): void {}
        setCenter(): void {}
        setZoom(): void {}
      },
      Marker: class {
        constructor(options?: google.maps.MarkerOptions) {
          if (options) {
            markerOptions.push(options);
          }
        }
        setMap(): void {}
        setIcon(): void {}
        setPosition(): void {}
        setTitle(): void {}
        addListener(): void {}
      },
      event: {
        trigger(): void {},
      },
      importLibrary: vi.fn().mockResolvedValue({}),
    } as unknown as typeof google.maps,
  };
}

describe('ActivityGoogleMap', () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      get: () => 800,
    });
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get: () => 600,
    });
    installGoogleMaps();
  });

  afterEach(() => {
    Reflect.deleteProperty(window, 'google');
  });

  it('uses the activity-type icon instead of the default Google pin', async () => {
    render(
      <ActivityGoogleMap
        locale="en"
        listings={[buildListing()]}
        selectedId="act-1"
        onSelect={() => undefined}
        ariaLabel="Activity map"
      />,
    );

    await waitFor(() => {
      expect(markerOptions).toHaveLength(1);
    });

    const icon = markerOptions[0]?.icon;
    expect(icon).toMatchObject({
      url: expect.stringContaining(iconSrcForActivity('workshop')),
    });
  });

  it('creates the map on first mount before listings arrive', async () => {
    const { rerender } = render(
      <ActivityGoogleMap
        locale="en"
        listings={[]}
        selectedId={null}
        onSelect={() => undefined}
        ariaLabel="Activity map"
      />,
    );

    await waitFor(() => {
      expect(mapConstructors).toHaveLength(1);
    });

    rerender(
      <ActivityGoogleMap
        locale="en"
        listings={[buildListing()]}
        selectedId="act-1"
        onSelect={() => undefined}
        ariaLabel="Activity map"
      />,
    );

    await waitFor(() => {
      expect(markerOptions).toHaveLength(1);
    });
    expect(mapConstructors).toHaveLength(1);
  });
});
