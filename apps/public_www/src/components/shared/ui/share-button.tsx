'use client';

import { useEffect, useState } from 'react';

interface ShareButtonProps {
  readonly title: string;
  readonly label: string;
  readonly copiedLabel: string;
  readonly className?: string;
}

const COPIED_RESET_MS = 2500;

/** Web Share on phones; copies the link where Web Share is unavailable. */
export function ShareButton({
  title,
  label,
  copiedLabel,
  className = '',
}: ShareButtonProps) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }
    const timer = window.setTimeout(() => setCopied(false), COPIED_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function share() {
    const url = window.location.href;
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share({ title, url });
        return;
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return;
        }
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <button
      type="button"
      onClick={() => void share()}
      className={
        'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border ' +
        'border-ink-900/15 bg-white px-4 text-sm font-semibold text-ink-900 ' +
        `transition hover:bg-brand-50 ${className}`
      }
    >
      <img
        src="/images/icons/share.svg"
        alt=""
        width={18}
        height={18}
        aria-hidden="true"
        className="h-[18px] w-[18px]"
      />
      <span aria-live="polite">{copied ? copiedLabel : label}</span>
    </button>
  );
}
