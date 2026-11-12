'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

interface ChoiceCarouselProps {
  readonly ariaLabel: string;
  readonly previousLabel: string;
  readonly nextLabel: string;
  readonly children: ReactNode;
}

const ARROW_CLASS_NAME =
  'absolute top-1/2 z-10 hidden h-11 w-11 -translate-y-1/2 items-center ' +
  'justify-center rounded-full border border-ink-900/15 bg-white shadow-md ' +
  'transition hover:bg-brand-50 disabled:cursor-default disabled:opacity-40 ' +
  'md:inline-flex';

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

function pageStarts(last: number, visible: number): number[] {
  const starts = [0];
  for (let start = visible; start < last; start += visible) {
    starts.push(start);
  }
  if (last > 0 && starts[starts.length - 1] !== last) {
    starts.push(last);
  }
  return starts;
}

export function ChoiceCarousel({
  ariaLabel,
  previousLabel,
  nextLabel,
  children,
}: ChoiceCarouselProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canScrollBack, setCanScrollBack] = useState(false);
  const [canScrollForward, setCanScrollForward] = useState(true);

  const updateArrows = useCallback(() => {
    const track = trackRef.current;
    if (!track || track.clientWidth === 0) {
      return;
    }
    setCanScrollBack(track.scrollLeft > 4);
    setCanScrollForward(
      track.scrollLeft + track.clientWidth < track.scrollWidth - 4,
    );
  }, []);

  useEffect(() => {
    updateArrows();
    const track = trackRef.current;
    if (!track || typeof ResizeObserver !== 'function') {
      return undefined;
    }
    const observer = new ResizeObserver(updateArrows);
    observer.observe(track);
    return () => observer.disconnect();
  }, [children, updateArrows]);

  function scrollByPage(direction: 1 | -1) {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    const card = track.firstElementChild;
    const cardWidth = card instanceof HTMLElement ? card.offsetWidth : 0;
    const gapValue = Number.parseFloat(window.getComputedStyle(track).columnGap);
    const gap = Number.isFinite(gapValue) ? gapValue : 0;
    const step = cardWidth + gap;
    const maxScroll = Math.max(0, track.scrollWidth - track.clientWidth);
    const behavior = prefersReducedMotion() ? 'auto' : 'smooth';
    if (step <= 0 || maxScroll <= 0) {
      track.scrollTo({ left: direction > 0 ? maxScroll : 0, behavior });
      return;
    }
    const visible = Math.max(1, Math.round(track.clientWidth / step));
    const last = Math.max(0, track.childElementCount - visible);
    const starts = pageStarts(last, visible);
    const positions = starts.map((start, index) =>
      index === starts.length - 1 && start > 0 ? maxScroll : start * step,
    );
    if (positions[positions.length - 1] < maxScroll - 4) {
      positions.push(maxScroll);
    }
    let current = 0;
    for (let index = 0; index < positions.length; index += 1) {
      if (track.scrollLeft + 4 >= positions[index]) {
        current = index;
      }
    }
    const next = Math.min(
      positions.length - 1,
      Math.max(0, current + direction),
    );
    track.scrollTo({ left: positions[next], behavior });
  }

  return (
    <div className="relative md:px-12">
      <div
        ref={trackRef}
        role="region"
        aria-label={ariaLabel}
        data-choice-carousel=""
        onScroll={updateArrows}
        className={
          'listing-carousel__track flex w-full min-w-0 max-w-full flex-wrap gap-2 ' +
          // gap-3 is 0.75rem. Activity cards use that twice in their width
          // so three of them fill this track with no horizontal scrollbar.
          'md:flex-nowrap md:gap-3 md:overflow-x-auto md:overscroll-x-contain'
        }
      >
        {children}
      </div>
      <button
        type="button"
        aria-label={previousLabel}
        disabled={!canScrollBack}
        onClick={() => scrollByPage(-1)}
        className={`${ARROW_CLASS_NAME} left-0`}
      >
        <img
          src="/images/ui/chevron-left.svg"
          alt=""
          width={14}
          height={14}
          aria-hidden="true"
          className="block h-3.5 w-3.5"
        />
      </button>
      <button
        type="button"
        aria-label={nextLabel}
        disabled={!canScrollForward}
        onClick={() => scrollByPage(1)}
        className={`${ARROW_CLASS_NAME} right-0`}
      >
        <img
          src="/images/ui/chevron-right.svg"
          alt=""
          width={14}
          height={14}
          aria-hidden="true"
          className="block h-3.5 w-3.5"
        />
      </button>
    </div>
  );
}
