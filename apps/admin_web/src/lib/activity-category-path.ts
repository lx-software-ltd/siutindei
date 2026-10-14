/**
 * Tree-order helpers for the admin Categories table.
 *
 * Siblings sort by display_order, then name, then id. The flat list is a
 * pre-order walk: a parent, then its descendants, then the next sibling.
 */

export interface CategoryPathNode {
  id: string;
  name: string;
  parent_id?: string | null;
  display_order?: number | null;
}

export function compareCategorySiblings(
  left: CategoryPathNode,
  right: CategoryPathNode
): number {
  const order = (left.display_order ?? 0) - (right.display_order ?? 0);
  if (order !== 0) {
    return order;
  }
  const name = left.name.localeCompare(right.name);
  if (name !== 0) {
    return name;
  }
  return left.id.localeCompare(right.id);
}

export function groupCategoriesByParent<T extends CategoryPathNode>(
  items: readonly T[]
): Map<string, T[]> {
  const knownIds = new Set(items.map((item) => item.id));
  const childrenByParent = new Map<string, T[]>();

  for (const item of items) {
    const parentId =
      item.parent_id && knownIds.has(item.parent_id) ? item.parent_id : '';
    const siblings = childrenByParent.get(parentId) ?? [];
    siblings.push(item);
    childrenByParent.set(parentId, siblings);
  }

  for (const siblings of childrenByParent.values()) {
    siblings.sort(compareCategorySiblings);
  }

  return childrenByParent;
}

export function flattenCategoriesByPathOrder<T extends CategoryPathNode>(
  items: readonly T[]
): T[] {
  const childrenByParent = groupCategoriesByParent(items);
  const ordered: T[] = [];

  function walk(nodes: readonly T[]) {
    for (const node of nodes) {
      ordered.push(node);
      walk(childrenByParent.get(node.id) ?? []);
    }
  }

  walk(childrenByParent.get('') ?? []);
  return ordered;
}
