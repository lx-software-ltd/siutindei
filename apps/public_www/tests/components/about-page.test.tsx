import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AboutPage } from '@/components/sections/about-page';
import { getContent } from '@/content';

const enAbout = getContent('en').pages.about;
const zhAbout = getContent('zh-HK').pages.about;

describe('AboutPage', () => {
  it('opens on the family story, with a section list like the privacy policy', () => {
    render(<AboutPage content={enAbout} contactEmail="hello@example.com" placeFull="Stanley, Hong Kong" />);

    expect(
      screen.getByRole('heading', { level: 1, name: 'Built for Hong Kong families' }),
    ).toBeInTheDocument();
    expect(screen.queryByText('About us')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Explore activities' }),
    ).not.toBeInTheDocument();
    expect(document.querySelector('[data-section-id="hero"]')).toBeNull();
    expect(document.querySelector('[data-section-id="about-page"]')).not.toBeNull();

    const article = document.querySelector('[data-section-id="about-page"]');
    expect(article?.textContent).toContain('Chung Hom Kok');
    expect(article?.textContent).toContain('Stanley');
    expect(article?.textContent).toContain('Repulse Bay');
    expect(article?.textContent).toContain('Ap Lei Chau');
    expect(article?.textContent).toContain('small businesses');
    expect(article?.textContent).toContain('manage your own page');

    const toc = screen.getByRole('navigation', { name: enAbout.onThisPageLabel });
    for (const section of enAbout.sections) {
      const heading = screen.getByRole('heading', {
        level: 2,
        name: section.heading,
      });
      expect(heading.closest('section')?.id).toBe(section.id);
      const link = Array.from(toc.querySelectorAll('a')).find(
        (anchor) => anchor.getAttribute('href') === `#${section.id}`,
      );
      expect(link?.textContent).toBe(section.heading);
    }

    const email = screen.getByRole('link', { name: 'hello@example.com' });
    expect(email).toHaveAttribute('href', 'mailto:hello@example.com');
    expect(email).toHaveClass('link-underlined');
    expect(email.closest('section')?.id).toBe('write-to-me');
  });

  it('omits the email link when no contact address is configured', () => {
    render(<AboutPage content={enAbout} contactEmail="  " placeFull="Stanley, Hong Kong" />);

    expect(screen.queryByRole('link', { name: /@/ })).not.toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Get in touch' }),
    ).toBeInTheDocument();
  });

  it('tells the same story in Chinese, with the same section ids', () => {
    expect(zhAbout.sections.map((section) => section.id)).toEqual(
      enAbout.sections.map((section) => section.id),
    );
    expect(new Set(enAbout.sections.map((section) => section.id)).size).toBe(
      enAbout.sections.length,
    );

    render(<AboutPage content={zhAbout} contactEmail="hello@example.com" placeFull="香港赤柱" />);

    expect(
      screen.getByRole('heading', { level: 1, name: '為香港家庭而設' }),
    ).toBeInTheDocument();
    const article = document.querySelector('[data-section-id="about-page"]');
    expect(article?.textContent).toContain('舂坎角');
    expect(article?.textContent).toContain('赤柱');
    expect(article?.textContent).toContain('淺水灣');
    expect(article?.textContent).toContain('鴨脷洲');
    expect(article?.textContent).toContain('小店');
    expect(
      screen.getByRole('link', { name: 'hello@example.com' }).closest('section')?.id,
    ).toBe('write-to-me');
  });

  it('answers what the site is and what parents ask, naming the covered area', () => {
    render(<AboutPage content={enAbout} contactEmail="" placeFull="Stanley, Hong Kong" />);

    const summary = screen.getByRole('heading', { level: 2, name: 'What is Siu Tin Dei' });
    expect(summary.closest('section')?.id).toBe('what-is-siu-tin-dei');
    expect(summary.closest('section')?.textContent).toContain('It lists activities in Stanley, Hong Kong today');
    for (const item of enAbout.questions.items) {
      expect(screen.getByRole('heading', { level: 3, name: item.question })).toBeInTheDocument();
    }
    expect(document.body.textContent).not.toContain('{placeFull}');
  });

  it('asks the same questions in Chinese', () => {
    expect(zhAbout.questions.items).toHaveLength(enAbout.questions.items.length);
    expect(zhAbout.summary.id).toBe(enAbout.summary.id);
  });
});
