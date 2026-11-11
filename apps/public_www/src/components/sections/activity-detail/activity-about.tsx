'use client';

import { useState } from 'react';

import { descriptionParagraphs } from '@/lib/activities/detail-view';

import { DetailSection } from './detail-section';
import type { ActivityDetailCopy } from './types';

const FOLD_AFTER_CHARACTERS = 420;

export function ActivityAbout({
  description,
  isTemplate,
  copy,
}: {
  readonly description: string;
  readonly isTemplate: boolean;
  readonly copy: ActivityDetailCopy;
}) {
  const [expanded, setExpanded] = useState(false);
  const paragraphs = descriptionParagraphs(description);
  if (paragraphs.length === 0) {
    if (!isTemplate) {
      return null;
    }
    return (
      <DetailSection id="about" title={copy.aboutHeading}>
        <p className="text-sm text-ink-500">{copy.detailsComingSoonLabel}</p>
      </DetailSection>
    );
  }
  const foldable = description.length > FOLD_AFTER_CHARACTERS;
  const folded = foldable && !expanded;
  return (
    <DetailSection id="about" title={copy.aboutHeading}>
      <div
        className={`max-w-prose space-y-4 whitespace-pre-line leading-7 text-ink-700 ${folded ? 'max-md:line-clamp-6' : ''}`}
      >
        {paragraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
      {foldable ? (
        <button
          type="button"
          aria-expanded={expanded}
          onClick={() => setExpanded((value) => !value)}
          className="mt-2 min-h-11 text-sm font-semibold text-ink-900 underline underline-offset-4 md:hidden"
        >
          {expanded ? copy.readLessLabel : copy.readMoreLabel}
        </button>
      ) : null}
    </DetailSection>
  );
}
