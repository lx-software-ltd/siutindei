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

/** Re-apply subcategories created in this session onto a freshly loaded tree. */
export function applyPublishedCategories(tree: ActivityCategoryNode[]) {
  return published.reduce(
    (current, node) => insertActivityCategory(current, node),
    tree
  );
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
