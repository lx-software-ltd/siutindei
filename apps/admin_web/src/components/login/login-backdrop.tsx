import type { ReactNode } from 'react';

const DRIFT = [
  'admin-login-bubble--drift-a',
  'admin-login-bubble--drift-b',
  'admin-login-bubble--drift-c',
] as const;

/** Fixed Hong Kong pictures. Slots follow the public hero, without random pick. */
const BUBBLES = [
  {
    src: '/images/small-world/bubble-junk.webp',
    className:
      'left-[3%] top-[10%] w-20 max-md:hidden md:left-[5%] md:w-28',
  },
  {
    src: '/images/small-world/bubble-tram.webp',
    className:
      'right-[3%] top-[16%] w-24 max-md:hidden md:right-[6%] md:w-36',
  },
  {
    src: '/images/small-world/bubble-clock-tower.webp',
    className:
      'bottom-[8%] left-[8%] w-16 max-md:hidden md:left-[12%] md:w-24',
  },
  {
    src: '/images/small-world/bubble-bauhinia.webp',
    className:
      'right-[5%] top-1/2 w-20 -translate-y-1/2 max-xl:hidden md:right-[8%] md:w-28',
  },
  {
    src: '/images/small-world/bubble-lantern.webp',
    className:
      'left-[10%] top-[42%] w-16 max-xl:hidden md:left-[14%] md:w-24',
  },
  {
    src: '/images/small-world/bubble-teacup.webp',
    className:
      'right-[10%] bottom-[12%] w-16 max-xl:hidden md:right-[14%] md:w-24',
  },
] as const;

interface LoginBackdropProps {
  children: ReactNode;
  footer?: ReactNode;
}

export function LoginBackdrop({ children, footer }: LoginBackdropProps) {
  return (
    <div className='flex min-h-screen flex-col'>
      <main className='admin-login-hero flex flex-1 flex-col items-center justify-center px-4 py-10 sm:px-6'>
        <div className='admin-login-hero__stars' aria-hidden='true' />
        <div className='pointer-events-none absolute inset-0' aria-hidden='true'>
          {BUBBLES.map((bubble, index) => (
            <img
              key={bubble.src}
              src={bubble.src}
              alt=''
              width={160}
              height={160}
              aria-hidden='true'
              loading='lazy'
              decoding='async'
              className={`admin-login-bubble ${DRIFT[index % DRIFT.length]} ${bubble.className}`}
            />
          ))}
        </div>
        <div className='relative z-10 w-full max-w-md'>{children}</div>
      </main>
      {footer}
    </div>
  );
}
