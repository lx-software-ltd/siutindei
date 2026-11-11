import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ListingCardMiniMap } from '@/components/sections/listings/listing-card-mini-map';
import type { ActivityListing } from '@/lib/activities/types';

const mapsEnabled = vi.hoisted(() => ({ value: true }));

vi.mock('@/lib/google-maps/config', () => ({
  isGoogleMapsEnabled: () => mapsEnabled.value,
  getGoogleMapsConfig: () => ({ apiKey: 'test-key' }),
}));

function buildListing(coordinate: {
  readonly lat: number | null;
  readonly lng: number | null;
}): ActivityListing {
  return {
    activity: {
      id: 'act-1',
      name: 'Kowloon art',
      description: null,
      nameTranslations: {},
      descriptionTranslations: {},
      ageMin: null,
      ageMax: null,
      categoryId: null,
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
      regionAreaId: null,
      address: null,
      lat: coordinate.lat,
      lng: coordinate.lng,
    },
    pricing: null,
    schedule: null,
  };
}

async function renderedMapImage(): Promise<HTMLImageElement> {
  const image = await waitFor(() => {
    const node = document.querySelector('img');
    expect(node).toBeInstanceOf(HTMLImageElement);
    return node as HTMLImageElement;
  });
  return image;
}

describe('ListingCardMiniMap', () => {
  it('keeps the photo whole until the static map image loads', async () => {
    mapsEnabled.value = true;
    const { container } = render(
      <ListingCardMiniMap
        locale="en"
        listing={buildListing({ lat: 22.3193, lng: 114.1694 })}
        mapAltLabel="Map location"
      />,
    );

    const image = await renderedMapImage();
    expect(image).toHaveAttribute('alt', '');
    expect(image.getAttribute('src')).toContain('staticmap');
    expect(container.querySelector('.listing-card-mini-map')).toBeNull();
    expect(screen.queryByRole('img', { name: /Map location/ })).toBeNull();

    fireEvent.load(image);

    expect(
      screen.getByRole('img', { name: 'Map location: Kowloon art' }),
    ).toBeInTheDocument();
    expect(container.querySelector('.listing-card-mini-map')).not.toBeNull();
  });

  it('removes the band when the static map image fails', async () => {
    mapsEnabled.value = true;
    const { container } = render(
      <ListingCardMiniMap
        locale="en"
        listing={buildListing({ lat: 22.2812, lng: 114.1289 })}
        mapAltLabel="Map location"
      />,
    );

    fireEvent.error(await renderedMapImage());

    await waitFor(() => {
      expect(container.querySelector('img')).toBeNull();
    });
    expect(container.querySelector('.listing-card-mini-map')).toBeNull();
    expect(screen.queryByText(/Map location/)).toBeNull();
  });

  it('renders nothing when the listing has no coordinates', () => {
    mapsEnabled.value = true;
    const { container } = render(
      <ListingCardMiniMap
        locale="en"
        listing={buildListing({ lat: null, lng: null })}
        mapAltLabel="Map location"
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing when Google Maps is not configured', () => {
    mapsEnabled.value = false;
    const { container } = render(
      <ListingCardMiniMap
        locale="en"
        listing={buildListing({ lat: 22.3193, lng: 114.1694 })}
        mapAltLabel="Map location"
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
