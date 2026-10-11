import type { GeographicAreaNode } from './api-client-user';

export interface NeighbourhoodFilterOption {
  id: string;
  name: string;
  group: string;
}

/**
 * Neighbourhoods, plus a district that has no children. Hong Kong
 * locations point at neighbourhoods. Other countries still use a
 * district leaf.
 */
export function neighbourhoodFilterOptions(
  tree: readonly GeographicAreaNode[]
): NeighbourhoodFilterOption[] {
  const options: NeighbourhoodFilterOption[] = [];

  function walk(nodes: readonly GeographicAreaNode[], group: string) {
    for (const node of nodes) {
      const children = node.children ?? [];
      if (node.level === 'neighbourhood') {
        options.push({ id: node.id, name: node.name, group });
        continue;
      }
      if (node.level === 'district' && children.length === 0) {
        options.push({ id: node.id, name: node.name, group });
        continue;
      }
      if (children.length === 0) {
        continue;
      }
      const nextGroup =
        node.level === 'country' ||
        node.level === 'region' ||
        node.level === 'city' ||
        node.level === 'district'
          ? node.name
          : group;
      walk(children, nextGroup);
    }
  }

  walk(tree, '');
  return options;
}

export function neighbourhoodOptionGroups(
  tree: readonly GeographicAreaNode[]
): [string, NeighbourhoodFilterOption[]][] {
  const groups = new Map<string, NeighbourhoodFilterOption[]>();
  for (const option of neighbourhoodFilterOptions(tree)) {
    const current = groups.get(option.group) ?? [];
    current.push(option);
    groups.set(option.group, current);
  }
  return Array.from(groups.entries());
}
