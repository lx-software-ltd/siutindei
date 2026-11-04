import type { NeighbourhoodFilterOption } from './neighbourhood-options';

/**
 * Catalog opens filtered to this English neighbourhood name.
 *
 * Change this string to switch the default. Use `''` for all
 * neighbourhoods. The id is resolved from the geographic area tree at
 * runtime, so it stays aligned with seeded Hong Kong neighbourhoods.
 */
export const DEFAULT_CATALOG_NEIGHBOURHOOD_NAME = 'Stanley';

/** Area id for the configured default, or `''` when unset or missing. */
export function areaIdForCatalogDefault(
  options: readonly NeighbourhoodFilterOption[]
): string {
  const name = DEFAULT_CATALOG_NEIGHBOURHOOD_NAME;
  if (!name) {
    return '';
  }
  return options.find((option) => option.name === name)?.id ?? '';
}
