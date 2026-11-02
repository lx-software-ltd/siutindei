import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AnalyticsConsentBanner } from '@/components/shared/analytics-consent-banner';
import enContent from '@/content/en.json';
import zhHKContent from '@/content/zh-HK.json';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';
import { withChromeCopy } from '../helpers/chrome-copy';

vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname,
}));

let mockPathname = '/en/';

describe('AnalyticsConsentBanner', () => {
  beforeEach(() => {
    mockPathname = '/en/';
    window.localStorage.clear();
    document.documentElement.setAttribute('data-gtm-id', 'GTM-TEST123');
  });

  afterEach(() => {
    document.documentElement.removeAttribute('data-gtm-id');
    document.documentElement.removeAttribute('data-meta-pixel-id');
  });

  it('shows the banner when analytics are configured and consent is unset', () => {
    render(withChromeCopy(<AnalyticsConsentBanner />));

    expect(
      screen.getByText(enContent.common.consent.message, { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: enContent.common.consent.privacyLinkLabel,
      }),
    ).toHaveAttribute('href', '/en/privacy#cookies');
  });

  it('stays hidden when analytics are not configured', () => {
    document.documentElement.removeAttribute('data-gtm-id');

    render(withChromeCopy(<AnalyticsConsentBanner />));

    expect(
      screen.queryByTestId('analytics-consent-banner'),
    ).not.toBeInTheDocument();
  });

  it('stays hidden when a consent decision is already stored', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'denied');

    render(withChromeCopy(<AnalyticsConsentBanner />));

    expect(
      screen.queryByTestId('analytics-consent-banner'),
    ).not.toBeInTheDocument();
  });

  it('stores consent and notifies the analytics scripts on accept', () => {
    const consentListener = vi.fn();
    window.addEventListener(
      'siutindei-analytics-consent-granted',
      consentListener,
    );

    render(withChromeCopy(<AnalyticsConsentBanner />));
    fireEvent.click(
      screen.getByRole('button', {
        name: enContent.common.consent.acceptLabel,
      }),
    );

    expect(window.localStorage.getItem(ANALYTICS_CONSENT_STORAGE_KEY)).toBe(
      'granted',
    );
    expect(consentListener).toHaveBeenCalledTimes(1);
    expect(
      screen.queryByTestId('analytics-consent-banner'),
    ).not.toBeInTheDocument();

    window.removeEventListener(
      'siutindei-analytics-consent-granted',
      consentListener,
    );
  });

  it('stores the refusal on decline without notifying analytics', () => {
    const consentListener = vi.fn();
    window.addEventListener(
      'siutindei-analytics-consent-granted',
      consentListener,
    );

    render(withChromeCopy(<AnalyticsConsentBanner />));
    fireEvent.click(
      screen.getByRole('button', {
        name: enContent.common.consent.declineLabel,
      }),
    );

    expect(window.localStorage.getItem(ANALYTICS_CONSENT_STORAGE_KEY)).toBe(
      'denied',
    );
    expect(consentListener).not.toHaveBeenCalled();
    expect(
      screen.queryByTestId('analytics-consent-banner'),
    ).not.toBeInTheDocument();

    window.removeEventListener(
      'siutindei-analytics-consent-granted',
      consentListener,
    );
  });

  it('renders localized copy on zh-HK pages', () => {
    mockPathname = '/zh-HK/search/';

    render(withChromeCopy(<AnalyticsConsentBanner />));

    expect(
      screen.getByText(zhHKContent.common.consent.message, { exact: false }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: zhHKContent.common.consent.privacyLinkLabel,
      }),
    ).toHaveAttribute('href', '/zh-HK/privacy#cookies');
  });
});
