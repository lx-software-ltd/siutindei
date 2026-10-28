'use client';

import type { DragEvent } from 'react';

import { Button } from '../../ui/button';

interface MediaGridProps {
  mediaUrls: string[];
  logoMediaUrl: string | null;
  isMediaBusy: boolean;
  dragIndex: number | null;
  dragOverIndex: number | null;
  onDragOver: (event: DragEvent<HTMLDivElement>, index: number) => void;
  onDrop: (event: DragEvent<HTMLDivElement>, index: number) => void;
  onDragStart: (event: DragEvent<HTMLButtonElement>, index: number) => void;
  onDragEnd: () => void;
  onSelectLogo: (url: string) => void;
  onMoveMedia: (fromIndex: number, toIndex: number) => void;
  onRemoveMedia: (index: number) => void;
}

export function MediaGrid({
  mediaUrls,
  logoMediaUrl,
  isMediaBusy,
  dragIndex,
  dragOverIndex,
  onDragOver,
  onDrop,
  onDragStart,
  onDragEnd,
  onSelectLogo,
  onMoveMedia,
  onRemoveMedia,
}: MediaGridProps) {
  return (
    <div className='grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3'>
      {mediaUrls.map((url, index) => {
        const isDropTarget = dragOverIndex === index && dragIndex !== null;
        const isFirst = index === 0;
        const isLast = index === mediaUrls.length - 1;
        return (
          <div
            key={`${url}-${index}`}
            className={`overflow-hidden rounded-lg border border-brand-100 ${
              isDropTarget ? 'ring-2 ring-sky-400' : ''
            }`}
            onDragOver={(event) => onDragOver(event, index)}
            onDrop={(event) => onDrop(event, index)}
          >
            <img
              src={url}
              alt={`Organization media ${index + 1}`}
              className='h-32 w-full object-cover sm:h-28'
              loading='lazy'
            />
            <div className='flex items-center justify-between gap-2 px-3 py-2 text-xs'>
              <div className='flex items-center gap-2'>
                <Button
                  type='button'
                  size='sm'
                  variant='ghost'
                  className='px-2 text-xs'
                  draggable={!isMediaBusy}
                  onDragStart={(event) => onDragStart(event, index)}
                  onDragEnd={onDragEnd}
                  disabled={isMediaBusy}
                >
                  Drag
                </Button>
                <label className='flex items-center gap-2 text-ink-700'>
                  <input
                    type='radio'
                    name='logo_media'
                    value={url}
                    checked={logoMediaUrl === url}
                    onChange={() => onSelectLogo(url)}
                    disabled={isMediaBusy}
                    className='h-3 w-3'
                  />
                  <span>Logo</span>
                </label>
              </div>
              <div className='flex items-center gap-1'>
                <Button
                  type='button'
                  size='sm'
                  variant='ghost'
                  onClick={() => onMoveMedia(index, index - 1)}
                  disabled={isMediaBusy || isFirst}
                >
                  Up
                </Button>
                <Button
                  type='button'
                  size='sm'
                  variant='ghost'
                  onClick={() => onMoveMedia(index, index + 1)}
                  disabled={isMediaBusy || isLast}
                >
                  Down
                </Button>
              </div>
            </div>
            <div className='flex items-center justify-between gap-2 px-3 pb-3 text-xs'>
              <a
                href={url}
                target='_blank'
                rel='noreferrer'
                className='truncate text-ink-700 hover:text-ink-900'
              >
                Open
              </a>
              <Button
                type='button'
                size='sm'
                variant='danger'
                onClick={() => onRemoveMedia(index)}
                disabled={isMediaBusy}
              >
                Remove
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
