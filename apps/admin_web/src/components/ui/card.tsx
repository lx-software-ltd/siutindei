import type { HTMLAttributes, ReactNode } from 'react';

import { clsx } from 'clsx';

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: string;
  /** `h3` when this card sits under the page heading. */
  titleLevel?: 'h2' | 'h3';
  titleAccessory?: ReactNode;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function Card({
  title,
  titleLevel = 'h2',
  titleAccessory,
  description,
  children,
  className = '',
  ...rest
}: CardProps) {
  const TitleTag = titleLevel === 'h3' ? 'h3' : 'h2';
  return (
    <section
      {...rest}
      className={clsx(
        'rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:rounded-xl sm:p-6',
        className
      )}
    >
      {(title || titleAccessory || description) && (
        <header className='mb-3 sm:mb-4'>
          {(title || titleAccessory) && (
            <div className='flex flex-wrap items-center gap-2'>
              {title && (
                <TitleTag className='text-base font-semibold sm:text-lg'>{title}</TitleTag>
              )}
              {titleAccessory}
            </div>
          )}
          {description && (
            <p className='mt-1 text-xs text-slate-600 sm:text-sm'>
              {description}
            </p>
          )}
        </header>
      )}
      {children}
    </section>
  );
}
