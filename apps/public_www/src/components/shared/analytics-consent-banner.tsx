'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';

import { useChromeCopy } from '@/components/shared/chrome-copy';
import {
  ANALYTICS_CONSENT_GRANTED_EVENT,
  ANALYTICS_CONSENT_STORAGE_KEY,
} from '@/lib/analytics/consent';
import { getLocaleFromPath, localizeHref } from '@/lib/locale-routing';
import { ROUTES } from '@/lib/routes';

function readStoredConsent(): string | null {
  try {
    return window.localStorage.getItem(ANALYTICS_CONSENT_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeConsent(value: 'granted' | 'denied'): void {
  try {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, value);
  } catch {
    // Consent still applies for this page view even if storage is blocked.
  }
}

export function AnalyticsConsentBanner() {
  const pathname = usePathname();
  const locale = getLocaleFromPath(pathname ?? '/');
  const consentContent = useChromeCopy(locale).consent;
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (readStoredConsent() !== null) {
      return;
    }

    const analyticsConfigured =
      document.documentElement.hasAttribute('data-gtm-id') ||
      document.documentElement.hasAttribute('data-meta-pixel-id');
    setIsVisible(analyticsConfigured);
  }, []);

  if (!isVisible) {
    return null;
  }

  const privacyHref = localizeHref(`${ROUTES.privacy}#cookies`, locale);

  const handleAccept = () => {
    storeConsent('granted');
    window.dispatchEvent(new Event(ANALYTICS_CONSENT_GRANTED_EVENT));
    setIsVisible(false);
  };

  const handleDecline = () => {
    storeConsent('denied');
    setIsVisible(false);
  };

  return (
    <div
      role="region"
      aria-label={consentContent.privacyLinkLabel}
      className="fixed inset-x-0 bottom-0 z-[70] border-t border-brand-100 bg-white p-4 shadow-lg sm:p-5"
      data-testid="analytics-consent-banner"
    >
      <div className="mx-auto flex max-w-3xl flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
        <p className="text-sm leading-6 text-ink-700">
          {consentContent.message}{' '}
          <Link
            href={privacyHref}
            className="font-semibold text-brand-700 underline underline-offset-2"
          >
            {consentContent.privacyLinkLabel}
          </Link>
        </p>
        <div className="flex shrink-0 gap-3">
          <button
            type="button"
            onClick={handleDecline}
            className="rounded-md border border-brand-100 px-4 py-2 text-sm font-semibold text-ink-700 hover:bg-brand-50"
          >
            {consentContent.declineLabel}
          </button>
          <button
            type="button"
            onClick={handleAccept}
            className="rounded-md bg-ink-900 px-4 py-2 text-sm font-semibold text-white hover:bg-ink-700"
          >
            {consentContent.acceptLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
