import type { GeographicAreaNode } from './api-client-user';

/**
 * Catalog opens filtered to this English neighbourhood name.
 *
 * Change this string to switch the default. Use `''` for all
 * neighbourhoods. The id is resolved from neighbourhood rows in the
 * geographic area tree at runtime. Import-job deep links skip this
 * default in the Catalog panel.
 */
export const DEFAULT_CATALOG_NEIGHBOURHOOD_NAME = 'Stanley';

/** Area id for the configured default, or `''` when unset or missing. */
export function areaIdForCatalogDefault(
  tree: readonly GeographicAreaNode[]
): string {
  const name = DEFAULT_CATALOG_NEIGHBOURHOOD_NAME;
  if (!name) {
    return '';
  }
  if (tree.length === 0) {
    return '';
  }

  let found = '';
  function walk(nodes: readonly GeographicAreaNode[]) {
    for (const node of nodes) {
      if (found) {
        return;
      }
      if (node.level === 'neighbourhood' && node.name === name) {
        found = node.id;
        return;
      }
      if (node.children.length > 0) {
        walk(node.children);
      }
    }
  }
  walk(tree);

  if (
    !found &&
    process.env.NODE_ENV !== 'production' &&
    typeof console !== 'undefined'
  ) {
    console.warn(
      `Catalog default neighbourhood "${name}" is not in the geographic area tree.`
    );
  }
  return found;
}
