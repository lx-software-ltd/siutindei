import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Footer } from '@/components/sections/footer';
import { getContent } from '@/content';

describe('Footer', () => {
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;
  const originalEmail = process.env.NEXT_PUBLIC_EMAIL;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    process.env.NEXT_PUBLIC_EMAIL = 'hello@example.com';
  });

  afterEach(() => {
    if (originalWhatsapp === undefined) {
      delete process.env.NEXT_PUBLIC_WHATSAPP_URL;
    } else {
      process.env.NEXT_PUBLIC_WHATSAPP_URL = originalWhatsapp;
    }
    if (originalEmail === undefined) {
      delete process.env.NEXT_PUBLIC_EMAIL;
    } else {
      process.env.NEXT_PUBLIC_EMAIL = originalEmail;
    }
  });

  function renderFooter() {
    const content = getContent('en').footer;
    render(<Footer locale="en" content={content} />);
    return content;
  }

  it('sets a small logo beside the tagline on phones and stacks them from iPad up', () => {
    const content = renderFooter();

    const logo = screen.getByRole('contentinfo').querySelector('img');
    expect(logo).toHaveClass('w-20', 'md:w-40');
    const brand = logo?.parentElement;
    expect(brand).toHaveClass('col-span-2', 'flex', 'items-center', 'md:col-span-1', 'md:block');
    expect(brand).toContainElement(screen.getByText(content.tagline));
  });

  it('puts the link columns side by side under a full-width contact row on phones', () => {
    const content = renderFooter();

    const contact = screen.getByText(content.contactHeading, { selector: 'p' }).parentElement;
    expect(contact).toHaveClass('col-span-2', 'md:col-span-1');
    expect(contact?.parentElement).toHaveClass('grid', 'grid-cols-2');

    const email = screen.getByRole('link', { name: 'hello@example.com' });
    const whatsapp = screen.getByRole('link', { name: /WhatsApp/ });
    expect(email.closest('div')).toBe(whatsapp.closest('div'));
    expect(email.closest('div')).toHaveClass('flex', 'flex-wrap', 'md:block');

    for (const column of content.columns) {
      const heading = screen.getByText(column.title, { selector: 'p' });
      expect(heading.parentElement).not.toHaveClass('col-span-2');
      expect(heading.parentElement?.parentElement).toBe(contact?.parentElement);
    }
  });

  it('gives each link its own tap area on phones', () => {
    const content = renderFooter();

    const links = [
      screen.getByRole('link', { name: 'hello@example.com' }),
      screen.getByRole('link', { name: /WhatsApp/ }),
      ...content.columns.flatMap((column) =>
        column.links.map((link) => screen.getByRole('link', { name: link.label })),
      ),
    ];
    for (const link of links) {
      expect(link).toHaveClass('inline-block', 'py-1.5', 'md:py-0');
    }
  });

  it('uses compact vertical padding on phones', () => {
    renderFooter();

    const copyright = screen.getByText(/All rights reserved/);
    expect(copyright.parentElement).toHaveClass('py-6', 'sm:py-12');
  });
});
