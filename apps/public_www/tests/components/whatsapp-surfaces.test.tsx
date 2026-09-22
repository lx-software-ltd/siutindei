import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Footer } from '@/components/sections/footer';
import { WhatsappFab } from '@/components/shared/whatsapp-fab';
import { getContent } from '@/content';
import { ANALYTICS_CONSENT_STORAGE_KEY } from '@/lib/analytics/consent';

describe('WhatsApp analytics surfaces', () => {
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;

  beforeEach(() => {
    window.localStorage.clear();
    window.dataLayer = [];
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    window.localStorage.setItem(ANALYTICS_CONSENT_STORAGE_KEY, 'granted');
  });

  afterEach(() => {
    window.localStorage.clear();
    delete window.dataLayer;
    if (originalWhatsapp === undefined) {
      delete process.env.NEXT_PUBLIC_WHATSAPP_URL;
    } else {
      process.env.NEXT_PUBLIC_WHATSAPP_URL = originalWhatsapp;
    }
  });

  it('pushes whatsapp_footer from the footer link', () => {
    render(
      <Footer locale="en" content={getContent('en').footer} />,
    );

    fireEvent.click(screen.getByRole('link', { name: /WhatsApp/ }));

    expect(window.dataLayer).toEqual([
      { event: 'generate_lead', lead_type: 'whatsapp_footer' },
    ]);
  });

  it('pushes whatsapp_fab from the mobile FAB', () => {
    render(<WhatsappFab label="Chat on WhatsApp" />);

    fireEvent.click(screen.getByRole('link', { name: 'Chat on WhatsApp' }));

    expect(window.dataLayer).toEqual([
      { event: 'generate_lead', lead_type: 'whatsapp_fab' },
    ]);
  });
});
