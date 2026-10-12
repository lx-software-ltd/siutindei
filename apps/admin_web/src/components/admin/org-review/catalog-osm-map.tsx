'use client';

import { useEffect, useRef } from 'react';
import 'leaflet/dist/leaflet.css';

import type { CatalogMapPin } from '../../../lib/catalog-map-pins';

const HONG_KONG = { lat: 22.3193, lng: 114.1694 };

function leafletApi(
  mod: typeof import('leaflet') | { default: typeof import('leaflet') }
): typeof import('leaflet') {
  return 'default' in mod && mod.default ? mod.default : (mod as typeof import('leaflet'));
}

function popupHtml(pin: CatalogMapPin): HTMLElement {
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

export function CatalogOsmMap({
  pins,
  active,
}: {
  pins: readonly CatalogMapPin[];
  active: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import('leaflet').Map | null>(null);
  const layerRef = useRef<import('leaflet').LayerGroup | null>(null);
  const pinsRef = useRef(pins);
  const activeRef = useRef(active);
  const pinKey = pins.map((pin) => `${pin.id}:${pin.lat}:${pin.lng}`).join('|');

  useEffect(() => {
    pinsRef.current = pins;
  }, [pins]);

  useEffect(() => {
    activeRef.current = active;
  }, [active]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    let cancelled = false;
    void import('leaflet').then((leaflet) => {
      if (cancelled || !containerRef.current || mapRef.current) {
        return;
      }
      const L = leafletApi(leaflet);
      const map = L.map(containerRef.current, {
        center: [HONG_KONG.lat, HONG_KONG.lng],
        zoom: 11,
        scrollWheelZoom: true,
      });
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      syncOsmMarkers(L, map, layerRef.current, pinsRef.current);
      if (activeRef.current) {
        map.invalidateSize();
      }
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) {
      return;
    }
    void import('leaflet').then((leaflet) => {
      syncOsmMarkers(leafletApi(leaflet), map, layer, pinsRef.current);
      if (active) {
        map.invalidateSize();
      }
    });
  }, [active, pinKey]);

  return (
    <div
      ref={containerRef}
      className='h-[28rem] w-full rounded-md border border-slate-200'
      role='application'
      aria-label='Filtered organizations'
    />
  );
}

function syncOsmMarkers(
  L: typeof import('leaflet'),
  map: import('leaflet').Map,
  layer: import('leaflet').LayerGroup,
  pins: readonly CatalogMapPin[]
) {
  layer.clearLayers();
  if (pins.length === 0) {
    map.setView([HONG_KONG.lat, HONG_KONG.lng], 11);
    return;
  }
  const bounds = L.latLngBounds(pins.map((pin) => [pin.lat, pin.lng]));
  for (const pin of pins) {
    const latLng = L.latLng(pin.lat, pin.lng);
    const marker = L.circleMarker(latLng, {
      radius: 8,
      color: '#1d4ed8',
      fillColor: '#2563eb',
      fillOpacity: 0.95,
      weight: 2,
    });
    marker.bindPopup(popupHtml(pin));
    marker.addTo(layer);
  }
  if (pins.length === 1) {
    map.setView([pins[0].lat, pins[0].lng], 14);
    return;
  }
  map.fitBounds(bounds, { padding: [48, 48] });
}
