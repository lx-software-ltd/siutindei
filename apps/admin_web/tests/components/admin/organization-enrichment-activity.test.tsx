import { describe, expect, it } from 'vitest';

import {
  enrichmentActivityCopy,
  leafletPresetIds,
} from '@/components/admin/organization-enrichment';
import { leafletUploadBody } from '@/lib/api-client-enrichment';

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

  it('names a leaflet while the file is being read', () => {
    expect(enrichmentActivityCopy('queued', 'leaflet')).toBe(
      'Reading the leaflet…'
    );
    expect(enrichmentActivityCopy('running', 'leaflet')).toBe(
      'Reading the leaflet…'
    );
    expect(enrichmentActivityCopy('extracting', 'leaflet')).toBe(
      'Reading pages with the model…'
    );
  });
});

describe('leafletPresetIds', () => {
  const picture = {
    id: 'media-1',
    status: 'pending',
    proposed_value: { leaflet: true },
  };
  const description = {
    id: 'desc-1',
    status: 'pending',
    proposed_value: { description: 'Saturday art' },
  };

  it('selects a picture the first time it arrives', () => {
    expect(leafletPresetIds([description, picture], [])).toEqual(['media-1']);
  });

  it('leaves a picture alone after it has been offered', () => {
    expect(leafletPresetIds([picture], ['media-1'])).toEqual([]);
  });
});

describe('leafletUploadBody', () => {
  it('posts the signed fields and then the file', () => {
    const file = new File([new Uint8Array([1, 2, 3])], 'flyer.png', {
      type: 'image/png',
    });
    const body = leafletUploadBody(
      { key: 'organizations/org/enrichment/leaflets/incoming/flyer.png', policy: 'abc' },
      file
    );
    expect(body.get('key')).toBe(
      'organizations/org/enrichment/leaflets/incoming/flyer.png'
    );
    expect(body.get('policy')).toBe('abc');
    expect(body.get('file')).toBe(file);
  });
});
