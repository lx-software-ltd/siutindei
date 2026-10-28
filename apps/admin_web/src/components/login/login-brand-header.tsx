import type { ReactNode } from 'react';
import Image from 'next/image';

interface LoginBrandHeaderProps {
  title?: ReactNode;
  subtitle?: string;
}

export function LoginBrandHeader({ title, subtitle }: LoginBrandHeaderProps) {
  return (
    <div className='mb-6 text-center'>
      <Image
        src='/images/brand/siutindei-logo-stacked.svg'
        alt='Siu Tin Dei'
        width={175}
        height={150}
        priority
        className='mx-auto h-auto w-32 md:w-40 xl:w-48'
      />
      <p className='mt-4 inline-flex rounded-full bg-ink-900 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-brand-100'>
        Admin console
      </p>
      {title ? (
        <h1 className='brand-title mt-4 text-2xl font-bold leading-tight text-ink-900 md:text-3xl xl:text-4xl'>
          {title}
        </h1>
      ) : null}
      {subtitle ? (
        <p className='mt-3 text-balance text-sm text-ink-700 md:text-base'>
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
