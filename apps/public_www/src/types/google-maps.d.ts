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
    mapTypeControl?: boolean;
    streetViewControl?: boolean;
    fullscreenControl?: boolean;
    gestureHandling?: 'auto' | 'cooperative' | 'greedy' | 'none';
  }

  class Map {
    constructor(element: HTMLElement, options?: MapOptions);
    fitBounds(bounds: LatLngBounds, padding?: number): void;
    panTo(latLng: LatLng): void;
    setCenter(latLng: LatLng): void;
    setZoom(zoom: number): void;
    setOptions(options: MapOptions): void;
  }

  interface Icon {
    url?: string;
    scaledSize?: Size;
    anchor?: Point;
    labelOrigin?: Point;
  }

  interface MarkerLabel {
    text: string;
    color?: string;
    fontSize?: string;
    fontWeight?: string;
  }

  interface MarkerOptions {
    map?: Map;
    position?: LatLng;
    title?: string;
    icon?: Icon | string;
  }

  class Marker {
    constructor(options?: MarkerOptions);
    setMap(map: Map | null): void;
    setIcon(icon: Icon | string): void;
    setPosition(position: LatLng): void;
    setTitle(title: string): void;
    setLabel(label: MarkerLabel | string | null): void;
    setZIndex(zIndex: number): void;
    addListener(eventName: string, handler: () => void): void;
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
}
