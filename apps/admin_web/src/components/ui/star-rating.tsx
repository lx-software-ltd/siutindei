'use client';

import { StarIcon } from '../icons/action-icons';

interface StarRatingProps {
  value: number;
  max?: number;
  onChange: (value: number) => void;
  sizeClassName?: string;
}

export function StarRating({
  value,
  max = 5,
  onChange,
  sizeClassName = 'h-5 w-5',
}: StarRatingProps) {
  const clampedValue = Math.max(0, Math.min(value, max));
  const stars = Array.from({ length: max }, (_, index) => index + 1);

  return (
    <div className='flex items-center gap-1'>
      {stars.map((starValue) => {
        const isSelected = starValue <= clampedValue;
        return (
          <button
            key={starValue}
            type='button'
            onClick={() => onChange(starValue)}
            className='rounded-sm p-0.5'
            aria-label={`Set rating to ${starValue} ${
              starValue === 1 ? 'star' : 'stars'
            }`}
          >
            <StarIcon
              className={`${sizeClassName} ${
                isSelected ? 'text-yellow-400' : 'text-slate-300'
              }`}
            />
          </button>
        );
      })}
    </div>
  );
}

