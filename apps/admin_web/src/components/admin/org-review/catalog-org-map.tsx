'use client';

import { useEffect, useRef, useState } from 'react';

import { StatusBanner } from '../../status-banner';
import { getGoogleMapsApiKey } from '../../../lib/config';
import { loadGoogleMapsScript } from '../../../lib/google-maps-script';
import type { CatalogMapPin } from '../../../lib/catalog-map-pins';

interface CatalogOrgMapProps {
  pins: readonly CatalogMapPin[];
  missingPinCount: number;
  truncated: boolean;
  isLoading: boolean;
  error: string;
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

function syncMarkers(
  map: google.maps.Map,
  info: google.maps.InfoWindow,
  markers: google.maps.Marker[],
  pins: readonly CatalogMapPin[]
) {
  for (const marker of markers) {
    marker.setMap(null);
  }
  markers.length = 0;
  if (pins.length === 0) {
    return;
  }
  const bounds = new google.maps.LatLngBounds();
  for (const pin of pins) {
    const position = new google.maps.LatLng(pin.lat, pin.lng);
    bounds.extend(position);
    const marker = new google.maps.Marker({
      map,
      position,
      title: pin.orgName,
    });
    marker.addListener('click', () => {
      info.setContent(pinContent(pin));
      info.open({ map, anchor: marker });
    });
    markers.push(marker);
  }
  if (pins.length === 1) {
    map.setCenter(new google.maps.LatLng(pins[0].lat, pins[0].lng));
    map.setZoom(14);
    return;
  }
  map.fitBounds(bounds, 48);
}

function CatalogGoogleMap({ pins }: { pins: readonly CatalogMapPin[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markersRef = useRef<google.maps.Marker[]>([]);
  const infoRef = useRef<google.maps.InfoWindow | null>(null);
  const pinsRef = useRef(pins);
  const [failed, setFailed] = useState(false);
  const apiKey = getGoogleMapsApiKey();
  const pinKey = pins.map((pin) => `${pin.id}:${pin.lat}:${pin.lng}`).join('|');

  useEffect(() => {
    pinsRef.current = pins;
  }, [pins]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !apiKey) {
      return;
    }
    let cancelled = false;
    loadGoogleMapsScript(apiKey)
      .then(() => {
        if (cancelled || !containerRef.current) {
          return;
        }
        const map =
          mapRef.current ??
          new google.maps.Map(containerRef.current, {
            center: new google.maps.LatLng(22.3193, 114.1694),
            zoom: 11,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
          });
        mapRef.current = map;
        infoRef.current = infoRef.current ?? new google.maps.InfoWindow();
        syncMarkers(map, infoRef.current, markersRef.current, pinsRef.current);
        google.maps.event.trigger(map, 'resize');
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey, pinKey]);

  if (!apiKey) {
    return (
      <StatusBanner kind='info'>
        The map uses the public website Google Maps key. It is not set for
        this admin app.
      </StatusBanner>
    );
  }
  if (failed) {
    return (
      <StatusBanner kind='error'>Google Maps failed to load.</StatusBanner>
    );
  }
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
  isLoading,
  error,
}: CatalogOrgMapProps) {
  return (
    <div className='space-y-3'>
      {error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      {isLoading && pins.length === 0 ? (
        <p className='text-sm text-slate-500'>Loading the map…</p>
      ) : null}
      {truncated ? (
        <StatusBanner kind='info'>
          The map stops after the first 2,000 matching organizations.
        </StatusBanner>
      ) : null}
      {missingPinCount > 0 ? (
        <StatusBanner kind='info'>
          {missingPinCount === 1
            ? '1 organization has no map pin.'
            : `${missingPinCount} organizations have no map pin.`}
        </StatusBanner>
      ) : null}
      {!isLoading && pins.length === 0 ? (
        <p className='text-sm text-slate-500'>
          No mapped locations match these filters.
        </p>
      ) : null}
      {pins.length > 0 ? <CatalogGoogleMap pins={pins} /> : null}
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
