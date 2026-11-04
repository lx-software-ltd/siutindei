import { describe, expect, it } from 'vitest';

import { enrichmentActivityCopy } from '@/components/admin/organization-enrichment';

describe('enrichmentActivityCopy', () => {
  it('keeps the crawl sentence until the model stage', () => {
    expect(enrichmentActivityCopy('queued')).toBe('Reading the website…');
    expect(enrichmentActivityCopy('running')).toBe('Reading the website…');
  });

  it('names the model stage after the pages are stored', () => {
    expect(enrichmentActivityCopy('extracting')).toBe(
      'Reading pages with the model…'
    );
  });

  it('is quiet once the run has finished', () => {
    expect(enrichmentActivityCopy('ready')).toBeNull();
    expect(enrichmentActivityCopy('failed')).toBeNull();
  });
});
