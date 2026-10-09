'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchActiveAreas,
  type GeographicAreaNode,
} from '../lib/api-client';

/**
 * Shared hook to fetch and cache the active geographic area tree.
 *
 * Returns the full tree plus helpers for matching Nominatim results
 * and extracting country codes for autocomplete scoping.
 */
export function useGeographicAreas() {
  const [tree, setTree] = useState<GeographicAreaNode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const fetched = useRef(false);

  useEffect(() => {
    if (fetched.current) return;
    fetched.current = true;

    fetchActiveAreas()
      .then((res) => setTree(res.items))
      .catch(() => setTree([]))
      .finally(() => setIsLoading(false));
  }, []);

  // Nominatim files Hong Kong under China, so countrycodes=hk matches
  // nothing. When Hong Kong is in the tree, omit the filter.
  const codes = tree
    .filter((n) => n.level === 'country' && n.code)
    .map((n) => n.code!.toLowerCase());
  const countryCodes = codes.includes('hk') ? '' : codes.join(',');

  /**
   * Walk the tree and collect all nodes as a flat list.
   */
  const flatNodes = useCallback((): GeographicAreaNode[] => {
    const result: GeographicAreaNode[] = [];
    function walk(nodes: GeographicAreaNode[]) {
      for (const node of nodes) {
        result.push(node);
        if (node.children) walk(node.children);
      }
    }
    walk(tree);
    return result;
  }, [tree]);

  /**
   * Find the leaf area_id by matching a Nominatim country_code and
   * address components against the tree.
   *
   * Returns the full selection chain (country > ... > district) or null.
   */
  const matchNominatimResult = useCallback(
    (address: {
      country_code?: string;
      country?: string;
      suburb?: string;
      city_district?: string;
      quarter?: string;
      neighbourhood?: string;
      city?: string;
      town?: string;
      state?: string;
      county?: string;
    }): { areaId: string; chain: GeographicAreaNode[] } | null => {
      if (!address.country_code) return null;

      const cc = address.country_code.toUpperCase();
      const country = tree.find(
        (n) => n.level === 'country' && n.code === cc
      );
      if (!country) return null;

      // Collect candidate terms from Nominatim for matching at each level
      const terms = [
        address.suburb,
        address.city_district,
        address.quarter,
        address.neighbourhood,
        address.city,
        address.town,
        address.state,
        address.county,
      ]
        .filter(Boolean)
        .map((s) => s!.toLowerCase());

      // Walk down the tree, trying to match at each level
      const chain: GeographicAreaNode[] = [country];
      let current = country;

      while (current.children && current.children.length > 0) {
        const match = current.children.find((child) =>
          terms.some(
            (term) =>
              child.name.toLowerCase() === term ||
              term.includes(child.name.toLowerCase()) ||
              child.name.toLowerCase().includes(term)
          )
        );

        if (match) {
          chain.push(match);
          current = match;
        } else {
          break;
        }
      }

      // Return the deepest match found
      const leaf = chain[chain.length - 1];
      return { areaId: leaf.id, chain };
    },
    [tree]
  );

  return {
    tree,
    isLoading,
    countryCodes,
    flatNodes,
    matchNominatimResult,
  };
}
