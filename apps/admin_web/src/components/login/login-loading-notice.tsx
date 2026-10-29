export const ADMIN_SESSION_LOADING_COPY = 'Preparing your admin session…';

/** Session wait between sign-in and the console. No fill: the page shows through. */
export function LoginLoadingNotice() {
  return (
    <div
      role='status'
      aria-live='polite'
      className='flex w-full items-center justify-center gap-3'
    >
      <img
        src='/images/small-world/bubble-bao.webp'
        alt=''
        width={48}
        height={48}
        aria-hidden='true'
        decoding='async'
        className='admin-login-bao h-12 w-12 shrink-0'
      />
      <p className='text-sm text-ink-900'>{ADMIN_SESSION_LOADING_COPY}</p>
    </div>
  );
}
