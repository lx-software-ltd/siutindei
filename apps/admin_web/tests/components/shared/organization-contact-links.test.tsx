import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import {
  OrganizationContactLink,
  organizationEmailHref,
  organizationWebsiteHref,
  organizationWhatsappHref,
} from '@/components/shared/organizations/organization-contact-links';

describe('organizationEmailHref', () => {
  it('builds a mailto link for a valid address', () => {
    expect(organizationEmailHref('  contact@org-one.test ')).toBe(
      'mailto:contact@org-one.test'
    );
  });

  it('omits a link when the address is blank or invalid', () => {
    expect(organizationEmailHref('')).toBeNull();
    expect(organizationEmailHref('not-an-email')).toBeNull();
  });
});

describe('organizationWebsiteHref', () => {
  it('keeps an http or https address as typed', () => {
    expect(organizationWebsiteHref('https://org-one.example')).toBe(
      'https://org-one.example'
    );
    expect(organizationWebsiteHref('http://org-one.example/path')).toBe(
      'http://org-one.example/path'
    );
  });

  it('adds https when the protocol is missing', () => {
    expect(organizationWebsiteHref('www.org-one.example')).toBe(
      'https://www.org-one.example'
    );
  });

  it('refuses blank, oversized, and non-http values', () => {
    expect(organizationWebsiteHref('')).toBeNull();
    expect(organizationWebsiteHref('   ')).toBeNull();
    expect(organizationWebsiteHref('javascript:alert(1)')).toBeNull();
    expect(organizationWebsiteHref('https://user:pass@org-one.example')).toBeNull();
    expect(organizationWebsiteHref('a'.repeat(401))).toBeNull();
  });
});

describe('organizationWhatsappHref', () => {
  it('builds a wa.me link from the country code and number', () => {
    expect(organizationWhatsappHref('HK', '1234 5678')).toBe(
      'https://wa.me/85212345678'
    );
    expect(organizationWhatsappHref('hk', '91234567')).toBe(
      'https://wa.me/85291234567'
    );
  });

  it('omits a link when the number or country cannot be dialed', () => {
    expect(organizationWhatsappHref('HK', '')).toBeNull();
    expect(organizationWhatsappHref('', '91234567')).toBeNull();
    expect(organizationWhatsappHref('HK', '123')).toBeNull();
    expect(organizationWhatsappHref('ZZ', '91234567')).toBeNull();
  });
});

describe('OrganizationContactLink', () => {
  it('renders the action when a destination exists', () => {
    render(
      <OrganizationContactLink href='mailto:contact@org-one.test'>
        Send a new email
      </OrganizationContactLink>
    );
    expect(screen.getByRole('link', { name: 'Send a new email' })).toHaveAttribute(
      'href',
      'mailto:contact@org-one.test'
    );
  });

  it('opens an external destination in a new tab', () => {
    render(
      <OrganizationContactLink href='https://wa.me/85212345678' external>
        Start a new chat (whatsapp)
      </OrganizationContactLink>
    );
    const link = screen.getByRole('link', { name: 'Start a new chat (whatsapp)' });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer noopener');
  });

  it('renders nothing when there is no destination', () => {
    const { container } = render(
      <OrganizationContactLink href={null}>Open the website</OrganizationContactLink>
    );
    expect(container).toBeEmptyDOMElement();
  });
});
