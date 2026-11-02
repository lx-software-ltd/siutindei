import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LegalPage } from '@/components/sections/legal-page';
import { getLegalContent } from '@/lib/legal-copy';

const enContent = { legal: getLegalContent('en') };

describe('LegalPage', () => {
  it('renders the privacy policy with anchored sections', () => {
    render(
      <LegalPage
        document={enContent.legal.privacy}
        lastUpdatedLabel={enContent.legal.lastUpdatedLabel}
        lastUpdated={enContent.legal.lastUpdated}
        onThisPageLabel={enContent.legal.onThisPageLabel}
      />,
    );

    expect(
      screen.getByRole('heading', {
        level: 1,
        name: enContent.legal.privacy.title,
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        `${enContent.legal.lastUpdatedLabel}: ${enContent.legal.lastUpdated}`,
      ),
    ).toBeInTheDocument();

    for (const section of enContent.legal.privacy.sections) {
      const heading = screen.getByRole('heading', {
        level: 2,
        name: section.heading,
      });
      expect(heading.closest('section')?.id).toBe(section.id);
    }
  });

  it('links every section from the table of contents', () => {
    render(
      <LegalPage
        document={enContent.legal.terms}
        lastUpdatedLabel={enContent.legal.lastUpdatedLabel}
        lastUpdated={enContent.legal.lastUpdated}
        onThisPageLabel={enContent.legal.onThisPageLabel}
      />,
    );

    const toc = screen.getByRole('navigation', {
      name: enContent.legal.onThisPageLabel,
    });
    for (const section of enContent.legal.terms.sections) {
      const link = Array.from(toc.querySelectorAll('a')).find(
        (anchor) => anchor.getAttribute('href') === `#${section.id}`,
      );
      expect(link?.textContent).toBe(section.heading);
    }
  });
});
