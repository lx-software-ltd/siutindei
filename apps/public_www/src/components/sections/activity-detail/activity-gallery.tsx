'use client';

import { useRef, useState } from 'react';

import { Modal } from '@/components/shared/ui/modal';
import type { ActivityDetailCopy } from '@/components/sections/activity-detail/types';
import { formatTemplate } from '@/lib/format-template';
import { LISTING_IMAGE_HEIGHT, LISTING_IMAGE_WIDTH } from '@/lib/listing-image';

interface ActivityGalleryProps {
  readonly title: string;
  readonly imageUrls: readonly string[];
  readonly isLogo: boolean;
  readonly fallbackIconSrc: string;
  readonly copy: ActivityDetailCopy;
}

const MOSAIC_SMALL_TILES = 4;

function FallbackTile({
  iconSrc,
  label,
  className = '',
}: {
  readonly iconSrc: string;
  readonly label: string;
  readonly className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-3 bg-brand-50 text-sm text-ink-500 ${className}`}
    >
      <img src={iconSrc} alt="" width={96} height={96} aria-hidden="true" className="h-20 w-20 object-contain opacity-80" />
      <span>{label}</span>
    </div>
  );
}

export function ActivityGallery({
  title,
  imageUrls,
  isLogo,
  fallbackIconSrc,
  copy,
}: ActivityGalleryProps) {
  const [failed, setFailed] = useState<ReadonlySet<string>>(new Set());
  const [current, setCurrent] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  const trackRef = useRef<HTMLDivElement>(null);
  const photos = imageUrls.filter((url) => !failed.has(url));

  function markFailed(url: string) {
    setFailed((previous) => new Set(previous).add(url));
  }

  function handleScroll() {
    const track = trackRef.current;
    if (!track || track.clientWidth === 0) {
      return;
    }
    setCurrent(Math.round(track.scrollLeft / track.clientWidth));
  }

  if (photos.length === 0) {
    return (
      <FallbackTile
        iconSrc={fallbackIconSrc}
        label={copy.imageFallbackLabel}
        className="activity-gallery__frame aspect-[4/3] w-full rounded-2xl md:aspect-[16/7]"
      />
    );
  }

  const imageClassName = isLogo
    ? 'h-full w-full bg-white object-contain p-8'
    : 'h-full w-full object-cover';
  const smallTiles = photos.slice(1, 1 + MOSAIC_SMALL_TILES);
  const counter = formatTemplate(copy.photoCounterLabel, {
    current: Math.min(current + 1, photos.length),
    total: photos.length,
  });

  return (
    <section aria-label={copy.photosLabel} className="relative">
      <div
        ref={trackRef}
        onScroll={handleScroll}
        className="listing-carousel__track activity-gallery__frame flex snap-x snap-mandatory overflow-x-auto rounded-2xl md:hidden short:flex"
      >
        {photos.map((url, index) => (
          <div key={url} className="aspect-[4/3] w-full shrink-0 snap-start bg-brand-100">
            <img
              src={url}
              alt={index === 0 ? title : ''}
              width={LISTING_IMAGE_WIDTH}
              height={LISTING_IMAGE_HEIGHT}
              decoding="async"
              loading={index === 0 ? 'eager' : 'lazy'}
              {...(index === 0 ? { fetchPriority: 'high' as const } : {})}
              onError={() => markFailed(url)}
              className={imageClassName}
            />
          </div>
        ))}
      </div>
      {photos.length > 1 ? (
        <p className="pointer-events-none absolute bottom-3 right-3 rounded-full bg-ink-900/75 px-3 py-1 text-xs font-semibold text-white md:hidden short:block">
          {counter}
        </p>
      ) : null}

      <div
        className={
          smallTiles.length > 0
            ? 'activity-gallery__frame hidden h-[420px] gap-2 overflow-hidden rounded-2xl md:grid md:grid-cols-3 lg:grid-cols-4 lg:grid-rows-2 short:hidden'
            : 'activity-gallery__frame hidden h-[420px] overflow-hidden rounded-2xl md:block short:hidden'
        }
      >
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="relative h-full w-full overflow-hidden bg-brand-100 md:col-span-2 lg:row-span-2"
        >
          <img
            src={photos[0]}
            alt={title}
            width={LISTING_IMAGE_WIDTH}
            height={LISTING_IMAGE_HEIGHT}
            decoding="async"
            onError={() => markFailed(photos[0])}
            className={imageClassName}
          />
        </button>
        {smallTiles.map((url, index) => (
          <button
            key={url}
            type="button"
            onClick={() => setIsOpen(true)}
            className={`relative overflow-hidden bg-brand-100 ${index >= 2 ? 'hidden lg:block' : ''}`}
          >
            <img
              src={url}
              alt=""
              width={LISTING_IMAGE_WIDTH}
              height={LISTING_IMAGE_HEIGHT}
              loading="lazy"
              decoding="async"
              onError={() => markFailed(url)}
              className="h-full w-full object-cover"
            />
          </button>
        ))}
      </div>
      {photos.length > 1 ? (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="absolute bottom-4 right-4 hidden min-h-11 items-center rounded-lg border border-ink-900/15 bg-white px-4 text-sm font-semibold text-ink-900 shadow-sm hover:bg-brand-50 md:inline-flex short:hidden"
        >
          {formatTemplate(copy.showAllPhotosLabel, { count: photos.length })}
        </button>
      ) : null}

      <Modal isOpen={isOpen} title={copy.photosLabel} onClose={() => setIsOpen(false)}>
        <ul className="grid gap-3 sm:grid-cols-2">
          {photos.map((url) => (
            <li key={url} className="overflow-hidden rounded-xl bg-brand-100">
              <img
                src={url}
                alt=""
                width={LISTING_IMAGE_WIDTH}
                height={LISTING_IMAGE_HEIGHT}
                loading="lazy"
                decoding="async"
                className={isLogo ? 'w-full bg-white object-contain p-8' : 'w-full object-cover'}
              />
            </li>
          ))}
        </ul>
      </Modal>
    </section>
  );
}
