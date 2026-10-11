declare namespace google.maps {
  class LatLng {
    constructor(lat: number, lng: number);
  }

  class LatLngBounds {
    extend(point: LatLng): void;
  }

  class Size {
    constructor(width: number, height: number);
  }

  class Point {
    constructor(x: number, y: number);
  }

  interface MapOptions {
    center?: LatLng;
    zoom?: number;
    mapId?: string;
    mapTypeControl?: boolean;
    streetViewControl?: boolean;
    fullscreenControl?: boolean;
  }

  class Map {
    constructor(element: HTMLElement, options?: MapOptions);
    fitBounds(bounds: LatLngBounds, padding?: number): void;
    setCenter(latLng: LatLng): void;
    setZoom(zoom: number): void;
  }

  interface MarkerOptions {
    map?: Map;
    position?: LatLng;
    title?: string;
  }

  class Marker {
    constructor(options?: MarkerOptions);
    setMap(map: Map | null): void;
    addListener(eventName: string, handler: () => void): void;
  }

  class InfoWindow {
    constructor();
    setContent(content: HTMLElement | string): void;
    open(options: { map: Map; anchor: marker.AdvancedMarkerElement }): void;
    close(): void;
  }

  interface MapsEventListener {
    remove(): void;
  }

  namespace marker {
    interface AdvancedMarkerOptions {
      map?: Map | null;
      position?: LatLng;
      title?: string;
    }

    class AdvancedMarkerElement {
      constructor(options?: AdvancedMarkerOptions);
      map: Map | null;
      addListener(eventName: string, handler: () => void): MapsEventListener;
    }
  }

  const event: {
    trigger(instance: object, eventName: string): void;
  };

  function importLibrary(name: string): Promise<unknown>;
}

interface Window {
  google?: {
    maps: typeof google.maps;
  };
  gm_authFailure?: () => void;
}
