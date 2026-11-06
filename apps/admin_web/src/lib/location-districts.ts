/**
 * Approximate boxes for the 18 Hong Kong districts.
 *
 * Mirrors `backend/src/app/services/location_fix_districts.py`.
 * A pin is outside its district when it falls in a different district's
 * box, or outside Hong Kong. Gaps between boxes are not flagged.
 */

type Box = readonly [number, number, number, number];

const BOXES: Record<string, Box> = {
  'central-and-western': [22.268, 22.296, 114.122, 114.164],
  'wan-chai': [22.268, 22.288, 114.164, 114.21],
  eastern: [22.25, 22.298, 114.2, 114.255],
  southern: [22.205, 22.268, 114.115, 114.255],
  'yau-tsim-mong': [22.293, 22.33, 114.158, 114.182],
  'sham-shui-po': [22.322, 22.348, 114.13, 114.175],
  'kowloon-city': [22.308, 22.348, 114.175, 114.21],
  'wong-tai-sin': [22.332, 22.358, 114.18, 114.22],
  'kwun-tong': [22.292, 22.338, 114.208, 114.25],
  'kwai-tsing': [22.34, 22.378, 114.095, 114.148],
  'tsuen-wan': [22.355, 22.405, 114.065, 114.155],
  'tuen-mun': [22.365, 22.435, 113.91, 114.005],
  'yuen-long': [22.415, 22.535, 113.96, 114.105],
  north: [22.485, 22.565, 114.075, 114.235],
  'tai-po': [22.415, 22.515, 114.135, 114.285],
  'sha-tin': [22.355, 22.435, 114.165, 114.255],
  'sai-kung': [22.295, 22.485, 114.245, 114.43],
  islands: [22.18, 22.34, 113.82, 114.06],
};

const HONG_KONG: Box = [22.14, 22.58, 113.8, 114.45];

const ALIASES: Record<string, string> = {
  'central and western': 'central-and-western',
  中西區: 'central-and-western',
  'wan chai': 'wan-chai',
  灣仔: 'wan-chai',
  eastern: 'eastern',
  東區: 'eastern',
  southern: 'southern',
  南區: 'southern',
  'yau tsim mong': 'yau-tsim-mong',
  油尖旺: 'yau-tsim-mong',
  'sham shui po': 'sham-shui-po',
  深水埗: 'sham-shui-po',
  'kowloon city': 'kowloon-city',
  九龍城: 'kowloon-city',
  'wong tai sin': 'wong-tai-sin',
  黃大仙: 'wong-tai-sin',
  'kwun tong': 'kwun-tong',
  觀塘: 'kwun-tong',
  'kwai tsing': 'kwai-tsing',
  葵青: 'kwai-tsing',
  'tsuen wan': 'tsuen-wan',
  荃灣: 'tsuen-wan',
  'tuen mun': 'tuen-mun',
  屯門: 'tuen-mun',
  'yuen long': 'yuen-long',
  元朗: 'yuen-long',
  north: 'north',
  北區: 'north',
  'tai po': 'tai-po',
  大埔: 'tai-po',
  'sha tin': 'sha-tin',
  沙田: 'sha-tin',
  'sai kung': 'sai-kung',
  西貢: 'sai-kung',
  islands: 'islands',
  離島: 'islands',
};

export interface DistrictArea {
  id: string;
  name?: string | null;
  code?: string | null;
  name_translations?: Record<string, string | null> | null;
  children?: readonly DistrictArea[];
}

function contains(box: Box, lat: number, lng: number): boolean {
  const [south, north, west, east] = box;
  return south <= lat && lat <= north && west <= lng && lng <= east;
}

function containing(lat: number, lng: number): Set<string> {
  const found = new Set<string>();
  for (const [key, box] of Object.entries(BOXES)) {
    if (contains(box, lat, lng)) {
      found.add(key);
    }
  }
  return found;
}

function inHongKong(areas: readonly DistrictArea[]): boolean {
  return areas.some((area) => {
    if ((area.code ?? '').trim().toUpperCase() === 'HK') {
      return true;
    }
    const name = (area.name ?? '').trim().toLowerCase();
    return name === 'hong kong' || name === '香港';
  });
}

function labels(area: DistrictArea): string[] {
  const raw = [area.name, ...Object.values(area.name_translations ?? {})];
  return raw
    .map((value) => (value ?? '').trim())
    .filter((value) => value.length > 0);
}

export function districtKey(areas: readonly DistrictArea[]): string | null {
  if (!inHongKong(areas)) {
    return null;
  }
  for (const area of areas) {
    for (const label of labels(area)) {
      const key = ALIASES[label.toLowerCase()];
      if (key) {
        return key;
      }
    }
  }
  return null;
}

export function pinIsOutside(lat: number, lng: number, key: string): boolean {
  if (!(key in BOXES)) {
    return false;
  }
  const found = containing(lat, lng);
  if (found.has(key)) {
    return false;
  }
  if (found.size > 0) {
    return true;
  }
  return !contains(HONG_KONG, lat, lng);
}

export function pinOutsideDistrict(
  lat: number,
  lng: number,
  areas: readonly DistrictArea[]
): boolean {
  const key = districtKey(areas);
  if (!key) {
    return false;
  }
  return pinIsOutside(lat, lng, key);
}

/** The selected area, then each parent, ending at the root. */
export function areaAncestry(
  tree: readonly DistrictArea[],
  areaId: string
): DistrictArea[] {
  function walk(
    nodes: readonly DistrictArea[],
    chain: DistrictArea[]
  ): DistrictArea[] | null {
    for (const node of nodes) {
      const next = [...chain, node];
      if (node.id === areaId) {
        return [...next].reverse();
      }
      const found = walk(node.children ?? [], next);
      if (found) {
        return found;
      }
    }
    return null;
  }
  return walk(tree, []) ?? [];
}
