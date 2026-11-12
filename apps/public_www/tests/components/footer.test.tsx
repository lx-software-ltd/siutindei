import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { Footer } from '@/components/sections/footer';
import { getContent } from '@/content';

const INSTAGRAM_URL = 'https://www.instagram.com/studio_example';

describe('Footer', () => {
  const originalWhatsapp = process.env.NEXT_PUBLIC_WHATSAPP_URL;
  const originalEmail = process.env.NEXT_PUBLIC_EMAIL;
  const originalInstagram = process.env.NEXT_PUBLIC_INSTAGRAM_URL;

  beforeEach(() => {
    process.env.NEXT_PUBLIC_WHATSAPP_URL = 'https://wa.me/85200000000';
    process.env.NEXT_PUBLIC_EMAIL = 'hello@example.com';
    process.env.NEXT_PUBLIC_INSTAGRAM_URL = INSTAGRAM_URL;
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
    if (originalInstagram === undefined) {
      delete process.env.NEXT_PUBLIC_INSTAGRAM_URL;
    } else {
      process.env.NEXT_PUBLIC_INSTAGRAM_URL = originalInstagram;
    }
  });

  function renderFooter(locale: 'en' | 'zh-HK' = 'en') {
    const content = getContent(locale).footer;
    render(<Footer locale={locale} content={content} />);
    return content;
  }

  it('shows the logo without the LX Software tagline', () => {
    renderFooter();

    const logo = screen.getByRole('contentinfo').querySelector('img');
    expect(logo).toHaveAttribute('src', '/images/brand/siutindei-logo-stacked.svg');
    expect(logo).toHaveClass('w-20', 'md:w-40');
    expect(logo?.parentElement).toHaveClass('col-span-2', 'md:col-span-1');
    expect(screen.queryByText(/LX Software product/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Hong Kong, SAR/)).not.toBeInTheDocument();
    expect(screen.getByText(/All rights reserved/)).toBeInTheDocument();
  });

  it('drops the Chinese tagline as well', () => {
    renderFooter('zh-HK');

    expect(screen.queryByText(/香港特別行政區/)).not.toBeInTheDocument();
    expect(screen.getByText(/版權所有/)).toBeInTheDocument();
  });

  it('turns email, WhatsApp, and Instagram into icons', () => {
    const content = renderFooter();

    const email = screen.getByRole('link', { name: 'Email hello@example.com' });
    const whatsapp = screen.getByRole('link', { name: /WhatsApp/ });
    const instagram = screen.getByRole('link', { name: 'Instagram' });

    expect(email).toHaveAttribute('href', 'mailto:hello@example.com');
    expect(whatsapp).toHaveAttribute('href', 'https://wa.me/85200000000');
    expect(instagram).toHaveAttribute('href', INSTAGRAM_URL);
    expect(instagram).toHaveAttribute('target', '_blank');

    expect(email.querySelector('img')).toHaveAttribute('src', '/images/contact/email.svg');
    expect(whatsapp.querySelector('img')).toHaveAttribute('src', '/images/contact/whatsapp.svg');
    expect(instagram.querySelector('img')).toHaveAttribute('src', '/images/contact/instagram.svg');
    for (const link of [email, whatsapp, instagram]) {
      expect(link.querySelector('img')).toHaveClass('h-9', 'w-9');
    }

    expect(screen.queryByText('hello@example.com')).not.toBeInTheDocument();
    expect(screen.queryByText(/\+852/)).not.toBeInTheDocument();

    const icons = email.parentElement;
    expect(icons).toHaveClass('flex', 'flex-wrap');
    expect(email.closest('div')).toBe(whatsapp.closest('div'));
    expect(icons).toContainElement(instagram);
    for (const link of [email, whatsapp, instagram]) {
      expect(link).toHaveClass('inline-flex', 'h-11', 'w-11');
    }

    const contact = screen.getByText(content.contactHeading, { selector: 'p' }).parentElement;
    expect(contact).toContainElement(icons);
  });

  it('uses the Chinese email label on the icon', () => {
    renderFooter('zh-HK');

    expect(screen.getByRole('link', { name: '電郵 hello@example.com' })).toBeInTheDocument();
  });

  it('omits Instagram when no profile is configured', () => {
    delete process.env.NEXT_PUBLIC_INSTAGRAM_URL;
    renderFooter();

    expect(screen.queryByRole('link', { name: 'Instagram' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Email hello@example.com' })).toBeInTheDocument();
  });

  it('puts the link columns side by side under a full-width contact row on phones', () => {
    const content = renderFooter();

    const contact = screen.getByText(content.contactHeading, { selector: 'p' }).parentElement;
    expect(contact).toHaveClass('col-span-2', 'md:col-span-1');
    expect(contact?.parentElement).toHaveClass('grid', 'grid-cols-2');

    for (const column of content.columns) {
      const heading = screen.getByText(column.title, { selector: 'p' });
      expect(heading.parentElement).not.toHaveClass('col-span-2');
      expect(heading.parentElement?.parentElement).toBe(contact?.parentElement);
    }
  });

  it('gives each link its own tap area on phones', () => {
    const content = renderFooter();

    const iconLinks = [
      screen.getByRole('link', { name: 'Email hello@example.com' }),
      screen.getByRole('link', { name: /WhatsApp/ }),
      screen.getByRole('link', { name: 'Instagram' }),
    ];
    for (const link of iconLinks) {
      expect(link).toHaveClass('h-11', 'w-11');
    }

    const textLinks = content.columns.flatMap((column) =>
      column.links.map((link) => screen.getByRole('link', { name: link.label })),
    );
    for (const link of textLinks) {
      expect(link).toHaveClass('inline-block', 'py-1.5', 'md:py-0');
    }
  });

  it('keeps the copyright clear of the floating WhatsApp button on phones', () => {
    renderFooter();

    const copyright = screen.getByText(/All rights reserved/);
    expect(copyright.parentElement).toHaveClass('pb-20', 'pt-6', 'sm:py-12');
  });
});
