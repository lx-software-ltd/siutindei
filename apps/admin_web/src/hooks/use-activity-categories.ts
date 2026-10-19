'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  insertActivityCategory,
  publishedCategoriesSince,
  publishedCategoryCount,
  subscribeActivityCategories,
} from '../lib/activity-category-tree';
import {
  fetchActivityCategories,
  type ActivityCategoryNode,
} from '../lib/api-client';

/**
 * Shared hook to fetch and cache the activity category tree.
 */
export function useActivityCategories() {
  const [tree, setTree] = useState<ActivityCategoryNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;

    const publishedAtStart = publishedCategoryCount();
    fetchActivityCategories()
      .then((res) =>
        setTree(
          publishedCategoriesSince(publishedAtStart).reduce(
            (current, node) => insertActivityCategory(current, node),
            res.items
          )
        )
      )
      .catch(() => setTree([]))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(
    () =>
      subscribeActivityCategories((node) => {
        setTree((current) => insertActivityCategory(current, node));
      }),
    []
  );

  /**
   * Walk the tree and collect all nodes as a flat list.
   */
  const flatNodes = useCallback((): ActivityCategoryNode[] => {
    const result: ActivityCategoryNode[] = [];
    function walk(nodes: ActivityCategoryNode[]) {
      for (const node of nodes) {
        result.push(node);
        if (node.children) walk(node.children);
      }
    }
    walk(tree);
    return result;
  }, [tree]);

  return {
    tree,
    isLoading,
    flatNodes,
  };
}
