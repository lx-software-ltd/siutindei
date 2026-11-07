'use client';

import { useEffect, useRef, useState } from 'react';

import {
  getConfiguredGoogleMapsMapId,
  getGoogleMapsApiKey,
} from '../../lib/config';
import { loadGoogleMapsScript } from '../../lib/google-maps-script';
import {
  coordinateFromPosition,
  formatMapCoordinate,
  locationCoordinates,
  locationPinHint,
  pinMoveDelay,
} from '../../lib/location-maps';
import { StatusBanner } from '../status-banner';

const PIN_ZOOM = 17;

interface LocationPinMapProps {
  lat: string;
  lng: string;
  readOnly: boolean;
  /** Bumps when Reset should move the pin without waiting for typing. */
  jumpToken: number;
  onChange: (lat: string, lng: string) => void;
}

interface DraggablePin {
  setPosition(position: google.maps.LatLng): void;
  setDraggable(draggable: boolean): void;
  currentPosition(): unknown;
  clear(): void;
}

function publishDrag(
  position: unknown,
  onChange: (lat: string, lng: string) => void
) {
  const next = coordinateFromPosition(position);
  if (!next) {
    return;
  }
  onChange(formatMapCoordinate(next.lat), formatMapCoordinate(next.lng));
}

function standardPin(
  map: google.maps.Map,
  position: google.maps.LatLng,
  draggable: boolean,
  onChange: (lat: string, lng: string) => void
): DraggablePin {
  const marker = new google.maps.Marker({
    map,
    position,
    title: 'Location pin',
    draggable,
  });
  const listener = marker.addListener('dragend', () => {
    publishDrag(marker.getPosition(), onChange);
  });
  return {
    setPosition(next) {
      marker.setPosition(next);
    },
    setDraggable(next) {
      marker.setDraggable(next);
    },
    currentPosition() {
      return marker.getPosition();
    },
    clear() {
      listener.remove();
      marker.setMap(null);
    },
  };
}

function advancedPin(
  marker: google.maps.marker.AdvancedMarkerElement,
  draggable: boolean,
  onChange: (lat: string, lng: string) => void
): DraggablePin {
  marker.gmpDraggable = draggable;
  const listener = marker.addListener('dragend', () => {
    publishDrag(marker.position, onChange);
  });
  return {
    setPosition(next) {
      marker.position = next;
    },
    setDraggable(next) {
      marker.gmpDraggable = next;
    },
    currentPosition() {
      return marker.position;
    },
    clear() {
      listener.remove();
      marker.map = null;
    },
  };
}

function LocationGoogleMap({
  lat,
  lng,
  readOnly,
  jumpToken,
  onChange,
}: {
  lat: number;
  lng: number;
  readOnly: boolean;
  jumpToken: number;
  onChange: (lat: string, lng: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<google.maps.Map | null>(null);
  const pinRef = useRef<DraggablePin | null>(null);
  const onChangeRef = useRef(onChange);
  const latRef = useRef(lat);
  const lngRef = useRef(lng);
  const readOnlyRef = useRef(readOnly);
  const appliedJump = useRef(jumpToken);
  const [failed, setFailed] = useState(false);
  const [authRefused, setAuthRefused] = useState(false);
  const [ready, setReady] = useState(false);
  const apiKey = getGoogleMapsApiKey();

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    latRef.current = lat;
    lngRef.current = lng;
    readOnlyRef.current = readOnly;
  }, [lat, lng, readOnly]);

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
        const position = new google.maps.LatLng(latRef.current, lngRef.current);
        const mapId = getConfiguredGoogleMapsMapId();
        const map = new google.maps.Map(container, {
          center: position,
          zoom: PIN_ZOOM,
          ...(mapId ? { mapId } : {}),
          mapTypeControl: false,
          streetViewControl: false,
          fullscreenControl: false,
        });
        const report = (nextLat: string, nextLng: string) => {
          onChangeRef.current(nextLat, nextLng);
        };
        let pin: DraggablePin;
        if (mapId) {
          const library = (await google.maps.importLibrary('marker')) as {
            AdvancedMarkerElement: typeof google.maps.marker.AdvancedMarkerElement;
          };
          if (cancelled || !containerRef.current || !library.AdvancedMarkerElement) {
            if (!cancelled && !library.AdvancedMarkerElement) {
              setFailed(true);
            }
            return;
          }
          pin = advancedPin(
            new library.AdvancedMarkerElement({
              map,
              position,
              title: 'Location pin',
              gmpDraggable: !readOnlyRef.current,
            }),
            !readOnlyRef.current,
            report
          );
        } else {
          pin = standardPin(map, position, !readOnlyRef.current, report);
        }
        if (cancelled) {
          pin.clear();
          return;
        }
        mapRef.current = map;
        pinRef.current = pin;
        setReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
      pinRef.current?.clear();
      pinRef.current = null;
      mapRef.current = null;
      setReady(false);
    };
  }, [apiKey]);

  useEffect(() => {
    pinRef.current?.setDraggable(!readOnly);
  }, [readOnly, ready]);

  useEffect(() => {
    const pin = pinRef.current;
    const map = mapRef.current;
    if (!ready || !pin || !map) {
      return;
    }
    const immediate = jumpToken !== appliedJump.current;
    appliedJump.current = jumpToken;
    const delay = pinMoveDelay(
      coordinateFromPosition(pin.currentPosition()),
      { lat, lng },
      immediate
    );
    if (delay == null) {
      return;
    }
    const move = () => {
      const position = new google.maps.LatLng(lat, lng);
      pin.setPosition(position);
      map.setCenter(position);
    };
    if (delay === 0) {
      move();
      return;
    }
    const handle = window.setTimeout(move, delay);
    return () => {
      window.clearTimeout(handle);
    };
  }, [jumpToken, lat, lng, ready]);

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
  jumpToken,
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
      <p className='text-sm text-ink-500'>{locationPinHint(lat, lng, readOnly)}</p>
    );
  }
  return (
    <LocationGoogleMap
      lat={pin.lat}
      lng={pin.lng}
      readOnly={readOnly}
      jumpToken={jumpToken}
      onChange={onChange}
    />
  );
}
