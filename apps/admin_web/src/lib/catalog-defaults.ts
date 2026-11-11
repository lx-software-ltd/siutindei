import type { GeographicAreaNode } from './api-client-user';

/**
 * Catalog opens on the area named by the GitHub variable
 * `SEARCH_AREA_SCOPE`. `next.config.js` inlines it as
 * `NEXT_PUBLIC_SEARCH_AREA_SCOPE`.
 *
 * A blank value is every neighbourhood. One region id, district slug,
 * or neighbourhood slug (`southern-stanley`) selects that area. The
 * organisation list includes locations under it. Several areas that
 * do not sit inside one matched area leave the filter unset. An
 * import-job deep link skips this default in the Catalog panel.
 */
export function areaIdForCatalogDefault(
  tree: readonly GeographicAreaNode[],
  scope: string = configuredSearchAreaScope()
): string {
  const trimmed = scope.trim();
  const tokens = scopeTokens(trimmed);
  if (tokens.length === 0 || tree.length === 0) {
    return '';
  }

  const index = indexTree(tree);
  const matched: GeographicAreaNode[] = [];
  let unknown = false;
  for (const token of tokens) {
    const node = matchToken(index, token);
    if (!node) {
      unknown = true;
      continue;
    }
    matched.push(node);
  }

  const area = singleCoveringArea(matched, index.parentOf);
  if (!area) {
    warnDefault(
      `Catalog default from SEARCH_AREA_SCOPE "${trimmed}" is not a single area in the geographic area tree.`
    );
    return '';
  }
  if (unknown) {
    warnDefault(`SEARCH_AREA_SCOPE ignored unknown slugs in "${trimmed}".`);
  }
  return area.id;
}

/** English name of an area id, including a region or district default. */
export function areaNameInTree(
  tree: readonly GeographicAreaNode[],
  areaId: string
): string {
  if (!areaId) {
    return '';
  }
  let found = '';
  function walk(nodes: readonly GeographicAreaNode[]) {
    for (const node of nodes) {
      if (found) {
        return;
      }
      if (node.id === areaId) {
        found = node.name;
        return;
      }
      if (node.children.length > 0) {
        walk(node.children);
      }
    }
  }
  walk(tree);
  return found;
}

function configuredSearchAreaScope(): string {
  return (process.env.NEXT_PUBLIC_SEARCH_AREA_SCOPE ?? '').trim();
}

function warnDefault(message: string) {
  if (process.env.NODE_ENV === 'production' || typeof console === 'undefined') {
    return;
  }
  console.warn(message);
}

/** Same slug shape as public search and `hk_neighbourhoods._slug`. */
function scopeSlug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** Wizard region ids use underscores: `hong_kong_island`. */
function regionScopeId(name: string): string {
  return scopeSlug(name).replace(/-/g, '_');
}

function scopeTokens(raw: string): string[] {
  const seen = new Set<string>();
  const tokens: string[] = [];
  for (const part of raw.split(',')) {
    const token = part.trim().toLowerCase();
    if (!token || seen.has(token)) {
      continue;
    }
    seen.add(token);
    tokens.push(token);
  }
  return tokens;
}

interface ScopeIndex {
  regions: Map<string, GeographicAreaNode>;
  districts: Map<string, GeographicAreaNode>;
  neighbourhoods: Map<string, GeographicAreaNode>;
  parentOf: Map<string, string | null>;
}

function indexTree(tree: readonly GeographicAreaNode[]): ScopeIndex {
  const index: ScopeIndex = {
    regions: new Map(),
    districts: new Map(),
    neighbourhoods: new Map(),
    parentOf: new Map(),
  };

  function walk(
    nodes: readonly GeographicAreaNode[],
    parentId: string | null,
    districtSlug: string
  ) {
    for (const node of nodes) {
      index.parentOf.set(node.id, parentId);
      if (node.level === 'region') {
        const key = regionScopeId(node.name);
        if (key && !index.regions.has(key)) {
          index.regions.set(key, node);
        }
      }
      let nextDistrict = districtSlug;
      if (node.level === 'district') {
        nextDistrict = scopeSlug(node.name);
        if (nextDistrict && !index.districts.has(nextDistrict)) {
          index.districts.set(nextDistrict, node);
        }
      }
      if (node.level === 'neighbourhood') {
        const nameSlug = scopeSlug(node.name);
        if (districtSlug && nameSlug) {
          const key = `${districtSlug}-${nameSlug}`;
          if (!index.neighbourhoods.has(key)) {
            index.neighbourhoods.set(key, node);
          }
        }
      }
      if (node.children.length > 0) {
        walk(node.children, node.id, nextDistrict);
      }
    }
  }

  walk(tree, null, '');
  return index;
}

/**
 * Region id, then district slug, then `district-neighbourhood`.
 * `islands` is both a region id and a district slug; the region wins.
 */
function matchToken(
  index: ScopeIndex,
  token: string
): GeographicAreaNode | null {
  return (
    index.regions.get(token) ??
    index.districts.get(token) ??
    index.neighbourhoods.get(token) ??
    null
  );
}

/** The one matched area that contains every other match, if there is one. */
function singleCoveringArea(
  nodes: readonly GeographicAreaNode[],
  parentOf: ReadonlyMap<string, string | null>
): GeographicAreaNode | null {
  const unique: GeographicAreaNode[] = [];
  const seen = new Set<string>();
  for (const node of nodes) {
    if (seen.has(node.id)) {
      continue;
    }
    seen.add(node.id);
    unique.push(node);
  }
  const outermost = unique.filter((candidate) =>
    unique.every((other) => covers(candidate.id, other.id, parentOf))
  );
  return outermost.length === 1 ? outermost[0] : null;
}

function covers(
  ancestorId: string,
  nodeId: string,
  parentOf: ReadonlyMap<string, string | null>
): boolean {
  let current: string | null = nodeId;
  const seen = new Set<string>();
  while (current) {
    if (current === ancestorId) {
      return true;
    }
    if (seen.has(current)) {
      return false;
    }
    seen.add(current);
    const parent = parentOf.get(current);
    current = parent ?? null;
  }
  return false;
}
