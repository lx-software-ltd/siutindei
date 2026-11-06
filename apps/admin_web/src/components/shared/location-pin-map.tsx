'use client';

import { useEffect, useRef, useState } from 'react';

import { getGoogleMapsApiKey, getGoogleMapsMapId } from '../../lib/config';
import { loadGoogleMapsScript } from '../../lib/google-maps-script';
import {
  coordinateFromPosition,
  formatMapCoordinate,
  locationCoordinates,
} from '../../lib/location-maps';
import { StatusBanner } from '../status-banner';

const PIN_ZOOM = 17;

interface LocationPinMapProps {
  lat: string;
  lng: string;
  readOnly: boolean;
  onChange: (lat: string, lng: string) => void;
}

function LocationGoogleMap({
  lat,
  lng,
  readOnly,
  onChange,
}: {
  lat: number;
  lng: number;
  readOnly: boolean;
  onChange: (lat: string, lng: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const markerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null);
  const onChangeRef = useRef(onChange);
  const [failed, setFailed] = useState(false);
  const [authRefused, setAuthRefused] = useState(false);
  const apiKey = getGoogleMapsApiKey();

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    const previous = window.gm_authFailure;
    window.gm_authFailure = () => {
      setAuthRefused(true);
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
        const position = new google.maps.LatLng(lat, lng);
        const library = (await google.maps.importLibrary('marker')) as {
          AdvancedMarkerElement: typeof google.maps.marker.AdvancedMarkerElement;
        };
        if (cancelled || !containerRef.current || !library.AdvancedMarkerElement) {
          if (!cancelled && !library.AdvancedMarkerElement) {
            setFailed(true);
          }
          return;
        }
        const map =
          mapRef.current ??
          new google.maps.Map(containerRef.current, {
            center: position,
            zoom: PIN_ZOOM,
            mapId: getGoogleMapsMapId(),
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false,
          });
        mapRef.current = map;
        if (!markerRef.current) {
          const marker = new library.AdvancedMarkerElement({
            map,
            position,
            title: 'Location pin',
            gmpDraggable: !readOnly,
          });
          marker.addListener('dragend', () => {
            const next = coordinateFromPosition(marker.position);
            if (!next) {
              return;
            }
            onChangeRef.current(
              formatMapCoordinate(next.lat),
              formatMapCoordinate(next.lng),
            );
          });
          markerRef.current = marker;
        } else {
          markerRef.current.position = position;
          markerRef.current.gmpDraggable = !readOnly;
        }
        map.setCenter(position);
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [apiKey, lat, lng, readOnly]);

  useEffect(() => {
    return () => {
      if (markerRef.current) {
        markerRef.current.map = null;
        markerRef.current = null;
      }
      mapRef.current = null;
    };
  }, []);

  if (authRefused) {
    return (
      <StatusBanner kind='error'>
        Google Maps refused the key for this site. Add this admin address to
        the key&apos;s allowed websites.
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
      className='h-64 w-full rounded-md border border-brand-100'
      role='application'
      aria-label='Location pin'
    />
  );
}

export function LocationPinMap({
  lat,
  lng,
  readOnly,
  onChange,
}: LocationPinMapProps) {
  const pin = locationCoordinates({ lat, lng });
  if (!getGoogleMapsApiKey()) {
    return (
      <StatusBanner kind='info'>
        The map uses the public website Google Maps key. It is not set for
        this admin app.
      </StatusBanner>
    );
  }
  if (!pin) {
    return (
      <p className='text-sm text-ink-500'>
        Enter latitude and longitude to place the pin.
      </p>
    );
  }
  return (
    <LocationGoogleMap
      lat={pin.lat}
      lng={pin.lng}
      readOnly={readOnly}
      onChange={onChange}
    />
  );
}
