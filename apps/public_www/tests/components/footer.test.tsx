import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { Footer } from '@/components/sections/footer';
import { getContent } from '@/content';

describe('Footer', () => {
  it('places contact beside the logo and tagline at the lg breakpoint', () => {
    render(<Footer locale="en" content={getContent('en').footer} />);

    const tagline = screen.getByText('An LX Software product. Hong Kong, SAR.');
    const contactHeading = screen.getByText('Contact', { selector: 'p' });
    const brandRow = tagline.parentElement?.parentElement;

    expect(brandRow).toHaveClass('lg:grid-cols-2');
    expect(contactHeading.parentElement?.parentElement).toBe(brandRow);
    expect(contactHeading.parentElement).not.toBe(tagline.parentElement);
  });
});
