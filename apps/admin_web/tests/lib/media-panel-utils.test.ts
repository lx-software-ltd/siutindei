import { describe, expect, it } from 'vitest';

import { isManagedMediaUrl } from '@/components/admin/media/media-panel-utils';

describe('isManagedMediaUrl', () => {
  it('accepts an object on an Amazon S3 host', () => {
    expect(
      isManagedMediaUrl(
        'https://bucket.s3.ap-southeast-1.amazonaws.com/org/logo.png',
      ),
    ).toBe(true);
    expect(
      isManagedMediaUrl('https://s3.amazonaws.com/bucket/org/logo.png'),
    ).toBe(true);
    expect(
      isManagedMediaUrl('http://bucket.s3.amazonaws.com/org/logo.png'),
    ).toBe(true);
  });

  it('rejects a lookalike host or a URL that only mentions the suffix', () => {
    expect(
      isManagedMediaUrl('https://evil.example/amazonaws.com/org/logo.png'),
    ).toBe(false);
    expect(
      isManagedMediaUrl('https://amazonaws.com.evil.example/org/logo.png'),
    ).toBe(false);
    expect(isManagedMediaUrl('https://bucket.s3.amazonaws.com')).toBe(false);
    expect(isManagedMediaUrl('not a url')).toBe(false);
  });
});
