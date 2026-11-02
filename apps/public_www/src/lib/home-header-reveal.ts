'use client';

import { useEffect, useState } from 'react';

export const HERO_SEARCH_SENTINEL_ATTR = 'data-hero-search-sentinel';

const HERO_SEARCH_SENTINEL_SELECTOR =
  `[${HERO_SEARCH_SENTINEL_ATTR}]`;

export function shouldRevealHomeHeader(
  isSentinelIntersecting: boolean,
): boolean {
  return !isSentinelIntersecting;
}

function findHeroSearchSentinel(): Element | null {
  const node = document.querySelector(HERO_SEARCH_SENTINEL_SELECTOR);
  return node instanceof Element ? node : null;
}

/**
 * Reveals the home header once the hero search box leaves the viewport.
 * If the sentinel is not mounted yet, waits for it to appear.
 */
export function subscribeHomeHeaderReveal(
  onRevealChange: (isRevealed: boolean) => void,
): () => void {
  if (typeof IntersectionObserver === 'undefined') {
    return () => undefined;
  }

  let intersectionObserver: IntersectionObserver | null = null;

  function attach(sentinel: Element) {
    intersectionObserver = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      onRevealChange(shouldRevealHomeHeader(entry.isIntersecting));
    });
    intersectionObserver.observe(sentinel);
  }

  const existing = findHeroSearchSentinel();
  if (existing) {
    attach(existing);
    return () => {
      intersectionObserver?.disconnect();
    };
  }

  const mutationObserver = new MutationObserver(() => {
    const found = findHeroSearchSentinel();
    if (!found) {
      return;
    }
    mutationObserver.disconnect();
    attach(found);
  });
  mutationObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  return () => {
    mutationObserver.disconnect();
    intersectionObserver?.disconnect();
  };
}

export function useHomeHeaderReveal(isHome: boolean): boolean {
  const [isRevealed, setIsRevealed] = useState(!isHome);

  useEffect(() => {
    if (!isHome) {
      setIsRevealed(true);
      return;
    }

    setIsRevealed(false);
    return subscribeHomeHeaderReveal(setIsRevealed);
  }, [isHome]);

  return isRevealed;
}
