import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { TrackedWhatsappLink } from '@/components/shared/tracked-whatsapp-link';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

describe('TrackedWhatsappLink', () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.dataLayer = [];
  });

  afterEach(() => {
    window.localStorage.clear();
    delete window.dataLayer;
  });

  it('pushes generate_lead with the given lead type on click', () => {
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');

    render(
      <TrackedWhatsappLink
        href="https://wa.me/85200000000"
        leadType="whatsapp_footer"
      >
        WhatsApp
      </TrackedWhatsappLink>,
    );

    fireEvent.click(screen.getByRole('link', { name: 'WhatsApp' }));

    expect(window.dataLayer).toEqual([
      { event: 'generate_lead', lead_type: 'whatsapp_footer' },
    ]);
  });

  it('stays silent when consent is not granted', () => {
    render(
      <TrackedWhatsappLink
        href="https://wa.me/85200000000"
        leadType="whatsapp_footer"
      >
        Chat
      </TrackedWhatsappLink>,
    );

    fireEvent.click(screen.getByRole('link', { name: 'Chat' }));

    expect(window.dataLayer).toEqual([]);
  });
});
