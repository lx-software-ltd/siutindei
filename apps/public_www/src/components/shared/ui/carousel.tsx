'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

interface CarouselProps {
  readonly ariaLabel: string;
  readonly children: ReactNode;
  readonly previousLabel?: string;
  readonly nextLabel?: string;
}

const ARROW_CLASS_NAME =
  'carousel__arrow absolute top-1/3 z-10 hidden h-11 w-11 -translate-y-1/2 items-center ' +
  'justify-center rounded-full border border-ink-900/15 bg-white shadow-md transition ' +
  'hover:bg-brand-50 disabled:pointer-events-none disabled:opacity-0 pointer-fine:inline-flex';

export function Carousel({
  ariaLabel,
  children,
  previousLabel,
  nextLabel,
}: CarouselProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [canScrollBack, setCanScrollBack] = useState(false);
  const [canScrollForward, setCanScrollForward] = useState(false);
  const hasArrows = Boolean(previousLabel && nextLabel);

  const updateArrows = useCallback(() => {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    setCanScrollBack(track.scrollLeft > 4);
    setCanScrollForward(track.scrollLeft + track.clientWidth < track.scrollWidth - 4);
  }, []);

  useEffect(() => {
    if (!hasArrows) {
      return undefined;
    }
    updateArrows();
    const track = trackRef.current;
    if (!track || typeof ResizeObserver !== 'function') {
      return undefined;
    }
    const observer = new ResizeObserver(updateArrows);
    observer.observe(track);
    return () => observer.disconnect();
  }, [children, hasArrows, updateArrows]);

  function scrollByPage(direction: 1 | -1) {
    const track = trackRef.current;
    if (!track) {
      return;
    }
    track.scrollBy({ left: direction * track.clientWidth * 0.9, behavior: 'smooth' });
  }

  return (
    <div className="relative">
      <div
        ref={trackRef}
        onScroll={hasArrows ? updateArrows : undefined}
        className="listing-carousel__track flex gap-4 overflow-x-auto pb-2"
        role="region"
        aria-label={ariaLabel}
      >
        {children}
      </div>
      {hasArrows ? (
        <>
          <button
            type="button"
            aria-label={previousLabel}
            disabled={!canScrollBack}
            onClick={() => scrollByPage(-1)}
            className={`${ARROW_CLASS_NAME} -left-3`}
          >
            <img src="/images/ui/chevron-left.svg" alt="" width={14} height={14} aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            aria-label={nextLabel}
            disabled={!canScrollForward}
            onClick={() => scrollByPage(1)}
            className={`${ARROW_CLASS_NAME} -right-3`}
          >
            <img src="/images/ui/chevron-right.svg" alt="" width={14} height={14} aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        </>
      ) : null}
    </div>
  );
}
