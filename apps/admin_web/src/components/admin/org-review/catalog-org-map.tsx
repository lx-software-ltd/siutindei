'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { StatusBanner } from '../../status-banner';
import { getGoogleMapsApiKey, getGoogleMapsMapId } from '../../../lib/config';
import {
  CATALOG_MAPS_KEY_REFERRERS,
  catalogMapSurface,
} from '../../../lib/catalog-map-surface';
import { loadGoogleMapsScript } from '../../../lib/google-maps-script';
import {
  CATALOG_MAP_ORG_CAP,
  type CatalogMapPin,
} from '../../../lib/catalog-map-pins';
import { CatalogOsmMap } from './catalog-osm-map';

interface CatalogOrgMapProps {
  pins: readonly CatalogMapPin[];
  missingPinCount: number;
  truncated: boolean;
  /** More pages are still arriving. Stays true between those requests. */
  loadingMore: boolean;
  isLoading: boolean;
  /** False while the Table view is showing, so the map instance can stay alive. */
  active: boolean;
  error: string;
  orgCap?: number;
}

interface PinMarker {
  marker: google.maps.marker.AdvancedMarkerElement;
  listener: google.maps.MapsEventListener;
}

function pinContent(pin: CatalogMapPin): HTMLElement {
  const content = document.createElement('div');
  const title = document.createElement('p');
  title.textContent = pin.orgName;
  content.append(title);
  if (pin.areaName) {
    const area = document.createElement('p');
    area.textContent = pin.areaName;
    content.append(area);
  }
  if (pin.address) {
    const address = document.createElement('p');
    address.textContent = pin.address;
    content.append(address);
  }
  const link = document.createElement('a');
  link.href = pin.mapsUrl;
  link.target = '_blank';
  link.rel = 'noreferrer';
  link.textContent = `Open ${pin.orgName} in Google Maps`;
  content.append(link);
  return content;
}

function clearMarkers(markers: PinMarker[]) {
  for (const entry of markers) {
    entry.listener.remove();
    entry.marker.map = null;
  }
  markers.length = 0;
}

function syncMarkers(
  map: google.maps.Map,
  info: google.maps.InfoWindow,
  markers: PinMarker[],
  pins: readonly CatalogMapPin[],
  Marker: typeof google.maps.marker.AdvancedMarkerElement
) {
  clearMarkers(markers);
  if (pins.length === 0) {
    return;
  }
  const bounds = new google.maps.LatLngBounds();
  for (const pin of pins) {
    const position = new google.maps.LatLng(pin.lat, pin.lng);
    bounds.extend(position);
    const marker = new Marker({
      map,
      position,
      title: pin.orgName,
    });
    const listener = marker.addListener('click', () => {
      info.setContent(pinContent(pin));
      info.open({ map, anchor: marker });
    });
    markers.push({ marker, listener });
  }
  if (pins.length === 1) {
    map.setCenter(new google.maps.LatLng(pins[0].lat, pins[0].lng));
    map.setZoom(14);
    return;
  }
  map.fitBounds(bounds, 48);
}

function CatalogGoogleMap({
  pins,
  active,
  onAuthRefused,
  onFailed,
}: {
  pins: readonly CatalogMapPin[];
  active: boolean;
  onAuthRefused: () => void;
  onFailed: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<PinMarker[]>([]);
  const infoRef = useRef<google.maps.InfoWindow | null>(null);
  const markerCtorRef = useRef<typeof google.maps.marker.AdvancedMarkerElement | null>(
    null
  );
  const pinsRef = useRef(pins);
  const onAuthRefusedRef = useRef(onAuthRefused);
  const onFailedRef = useRef(onFailed);
  const apiKey = getGoogleMapsApiKey();
  const pinKey = pins.map((pin) => `${pin.id}:${pin.lat}:${pin.lng}`).join('|');

  useEffect(() => {
    pinsRef.current = pins;
  }, [pins]);

  useEffect(() => {
    onAuthRefusedRef.current = onAuthRefused;
    onFailedRef.current = onFailed;
  }, [onAuthRefused, onFailed]);

  useEffect(() => {
    const previous = window.gm_authFailure;
    window.gm_authFailure = () => {
      onAuthRefusedRef.current();
      previous?.();
    };
    return () => {
      window.gm_authFailure = previous;
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !apiKey) {
      return;
    }
    let cancelled = false;
    loadGoogleMapsScript(apiKey)
      .then(async () => {
        const library = (await google.maps.importLibrary('marker')) as {
          AdvancedMarkerElement: typeof google.maps.marker.AdvancedMarkerElement;
        };
        if (cancelled || !containerRef.current || !library.AdvancedMarkerElement) {
          if (!cancelled && !library.AdvancedMarkerElement) {
            onFailedRef.current();
          }
          return;
        }
        markerCtorRef.current = library.AdvancedMarkerElement;
        const map =
          mapRef.current ??
          new google.maps.Map(containerRef.current, {
            center: new google.maps.LatLng(22.3193, 114.1694),
            zoom: 11,
            mapId: getGoogleMapsMapId(),
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
          });
        mapRef.current = map;
        infoRef.current = infoRef.current ?? new google.maps.InfoWindow();
        syncMarkers(
          map,
          infoRef.current,
          markersRef.current,
          pinsRef.current,
          library.AdvancedMarkerElement
        );
        if (active) {
          google.maps.event.trigger(map, 'resize');
        }
      })
      .catch(() => {
        if (!cancelled) {
          onFailedRef.current();
        }
      });
    return () => {
      cancelled = true;
    };
  }, [active, apiKey, pinKey]);

  return (
    <div
      ref={containerRef}
      className='h-[28rem] w-full rounded-md border border-slate-200'
      role='application'
      aria-label='Filtered organizations'
    />
  );
}

export function CatalogOrgMap({
  pins,
  missingPinCount,
  truncated,
  loadingMore,
  isLoading,
  active,
  error,
  orgCap = CATALOG_MAP_ORG_CAP,
}: CatalogOrgMapProps) {
  const capLabel = orgCap.toLocaleString('en-US');
  const apiKey = getGoogleMapsApiKey();
  const [authRefused, setAuthRefused] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const onAuthRefused = useCallback(() => setAuthRefused(true), []);
  const onFailed = useCallback(() => setLoadFailed(true), []);
  const surface = catalogMapSurface({ apiKey, authRefused, loadFailed });
  const showFirstLoad = isLoading && pins.length === 0;
  const showEmpty = !isLoading && !loadingMore && pins.length === 0;
  return (
    <div className='space-y-3'>
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      {authRefused || loadFailed ? (
        <StatusBanner kind='info'>
          {`Google Maps blocked this admin host. The map uses OpenStreetMap until the public website key allows ${CATALOG_MAPS_KEY_REFERRERS.join(' and ')}.`}
        </StatusBanner>
      ) : null}
      {showFirstLoad ? (
        <p className='text-sm text-slate-500'>Loading the map…</p>
      ) : null}
      {loadingMore ? (
        <p className='text-sm text-slate-500'>Loading more locations…</p>
      ) : null}
      {truncated ? (
        <StatusBanner kind='info'>
          {`The map stops after the first ${capLabel} matching organizations.`}
        </StatusBanner>
      ) : null}
      {missingPinCount > 0 ? (
        <StatusBanner kind='info'>
          {missingPinCount === 1
            ? '1 organization has no map pin.'
            : `${missingPinCount} organizations have no map pin.`}
        </StatusBanner>
      ) : null}
      {showEmpty ? (
        <p className='text-sm text-slate-500'>
          No mapped locations match these filters.
        </p>
      ) : null}
      {surface === 'google' ? (
        <CatalogGoogleMap
          pins={pins}
          active={active}
          onAuthRefused={onAuthRefused}
          onFailed={onFailed}
        />
      ) : (
        <CatalogOsmMap pins={pins} active={active} />
      )}
      {pins.length > 0 ? (
        <ul className='space-y-2'>
          {pins.map((pin) => (
            <li key={pin.id} className='text-sm text-slate-700'>
              <span className='font-medium text-slate-900'>{pin.orgName}</span>
              {pin.areaName ? <span>{` · ${pin.areaName}`}</span> : null}
              {pin.address ? <span>{` · ${pin.address}`}</span> : null}
              <a
                className='ml-2 underline underline-offset-2'
                href={pin.mapsUrl}
                target='_blank'
                rel='noreferrer'
              >
                {`Open ${pin.orgName} in Google Maps`}
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
