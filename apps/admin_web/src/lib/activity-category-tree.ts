import type { ActivityCategoryNode } from './api-client';

type AppendListener = (node: ActivityCategoryNode) => void;

const appendListeners = new Set<AppendListener>();
const published: ActivityCategoryNode[] = [];

/** Insert `node` under its parent. The original tree is left unchanged. */
export function insertActivityCategory(
  tree: ActivityCategoryNode[],
  node: ActivityCategoryNode
): ActivityCategoryNode[] {
  const child: ActivityCategoryNode = {
    ...node,
    children: node.children ?? [],
  };
  if (!child.parent_id) {
    if (tree.some((item) => item.id === child.id)) {
      return tree;
    }
    return [...tree, child];
  }
  let placed = false;
  const walk = (nodes: ActivityCategoryNode[]): ActivityCategoryNode[] =>
    nodes.map((current) => {
      if (current.id === child.parent_id) {
        placed = true;
        const children = current.children ?? [];
        if (children.some((item) => item.id === child.id)) {
          return current;
        }
        return { ...current, children: [...children, child] };
      }
      if (!current.children?.length) {
        return current;
      }
      const nextChildren = walk(current.children);
      if (nextChildren === current.children) {
        return current;
      }
      return { ...current, children: nextChildren };
    });
  const next = walk(tree);
  return placed ? next : tree;
}

export function publishedCategoryCount() {
  return published.length;
}

/**
 * Subcategories published after `index`. A fetch applies only the ones
 * created while it was in flight, so a later fetch trusts the server
 * and does not restore a subcategory that was deleted.
 */
export function publishedCategoriesSince(index: number) {
  return published.slice(index);
}

/** Tell every mounted category tree about a subcategory that was just created. */
export function publishActivityCategory(node: ActivityCategoryNode) {
  published.push(node);
  for (const listener of appendListeners) {
    listener(node);
  }
}

export function resetPublishedActivityCategories() {
  published.length = 0;
}

export function subscribeActivityCategories(listener: AppendListener) {
  appendListeners.add(listener);
  return () => {
    appendListeners.delete(listener);
  };
}
