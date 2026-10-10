'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchActiveAreas,
  type GeographicAreaNode,
} from '../lib/api-client';

export interface NominatimAddress {
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
}

export interface NominatimAreaMatch {
  areaId: string;
  chain: GeographicAreaNode[];
}

function areaNameMatches(name: string, term: string): boolean {
  const normalized = name.toLowerCase();
  return (
    normalized === term ||
    term.includes(normalized) ||
    normalized.includes(term)
  );
}

/**
 * Match a Nominatim address to a leaf area.
 *
 * A district that still has neighbourhoods is not a location target, so
 * the match is dropped unless the walk reaches a childless area.
 */
export function matchNominatimAddress(
  tree: GeographicAreaNode[],
  address: NominatimAddress
): NominatimAreaMatch | null {
  if (!address.country_code) return null;

  const cc = address.country_code.toUpperCase();
  const country = tree.find(
    (node) => node.level === 'country' && node.code === cc
  );
  if (!country) return null;

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
    .filter((term): term is string => Boolean(term))
    .map((term) => term.toLowerCase());

  const chain: GeographicAreaNode[] = [country];
  let current = country;

  while (current.children.length > 0) {
    const match = current.children.find((child) =>
      terms.some((term) => areaNameMatches(child.name, term))
    );
    if (!match) break;
    chain.push(match);
    current = match;
  }

  if (current.children.length > 0) return null;
  return { areaId: current.id, chain };
}

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

  const matchNominatimResult = useCallback(
    (address: NominatimAddress): NominatimAreaMatch | null =>
      matchNominatimAddress(tree, address),
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
