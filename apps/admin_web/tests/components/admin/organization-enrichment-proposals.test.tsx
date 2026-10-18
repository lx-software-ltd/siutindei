import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  ProposalTable,
  selectionAfterToggle,
} from '@/components/admin/organization-enrichment-proposals';
import type { EnrichmentProposal } from '@/lib/api-client-enrichment';

vi.mock('@/hooks/use-activity-categories', () => ({
  useActivityCategories: () => ({
    tree: [],
    isLoading: false,
    flatNodes: () => [],
  }),
}));

vi.mock('@/hooks/use-geographic-areas', () => ({
  useGeographicAreas: () => ({
    tree: [],
    isLoading: false,
    countryCodes: '',
    flatNodes: () => [],
  }),
}));

const MEDIA_URL = 'https://cdn.example/class.png';

function proposal(patch: Partial<EnrichmentProposal>): EnrichmentProposal {
  return {
    id: 'prop-1',
    section: 'Organization',
    kind: 'update_organization',
    field: 'description',
    label: 'Description',
    current_value: null,
    proposed_value: { description: 'Saturday classes for children.' },
    confidence: 0.9,
    unverified: false,
    evidence: [],
    status: 'pending',
    ...patch,
  };
}

function renderTable(rows: EnrichmentProposal[]) {
  return render(
    <ProposalTable
      rows={rows}
      venues={[]}
      selected={[]}
      overrides={{}}
      onToggle={() => undefined}
      onOverride={() => undefined}
    />
  );
}

describe('ProposalTable place match', () => {
  it('shows the matched neighbourhood path', () => {
    renderTable([
      proposal({
        id: 'prop-location',
        section: 'Locations',
        kind: 'create_location',
        field: null,
        label: 'Location · Nathan Road',
        proposed_value: {
          address: '123 Nathan Road',
          area_id: 'area-mong-kok',
          area_path: 'Kowloon · Yau Tsim Mong · Mong Kok',
        },
      }),
    ]);

    expect(
      screen.getByText('Matched Kowloon · Yau Tsim Mong · Mong Kok.')
    ).toBeInTheDocument();
  });

  it('shows when the neighbourhood is outside the named district', () => {
    renderTable([
      proposal({
        id: 'prop-location',
        section: 'Locations',
        kind: 'create_location',
        field: null,
        label: 'Location · Nathan Road',
        proposed_value: {
          address: '123 Nathan Road',
          area_path: 'Kowloon · Yau Tsim Mong',
          area_note: 'The neighbourhood on the page is outside the named district.',
        },
      }),
    ]);

    expect(
      screen.getByText(
        'The neighbourhood on the page is outside the named district.'
      )
    ).toBeInTheDocument();
  });
});

describe('logo selection', () => {
  const rows = [
    proposal({
      id: 'logo-site',
      kind: 'add_media',
      field: 'logo',
      label: 'Logo',
      proposed_value: { source_url: MEDIA_URL, logo: true },
    }),
    proposal({
      id: 'logo-facebook',
      kind: 'add_media',
      field: 'logo',
      label: 'Logo · Facebook',
      proposed_value: { source_url: 'https://cdn.example/fb.jpg', logo: true },
    }),
    proposal({
      id: 'photo',
      kind: 'add_media',
      field: 'media',
      label: 'Photo 1',
      proposed_value: { source_url: 'https://cdn.example/photo.jpg', logo: false },
    }),
  ];

  it('keeps one logo selected', () => {
    const withSite = selectionAfterToggle([], 'logo-site', rows);
    const switched = selectionAfterToggle(withSite, 'logo-facebook', rows);
    const withPhoto = selectionAfterToggle(switched, 'photo', rows);

    expect(switched).toEqual(['logo-facebook']);
    expect(withPhoto).toEqual(['logo-facebook', 'photo']);
  });
});

describe('ProposalTable media preview', () => {
  it('shows the image instead of the source URL', () => {
    renderTable([
      proposal({
        id: 'prop-media',
        section: 'Media',
        kind: 'add_media',
        field: 'media',
        label: 'Photo 1',
        proposed_value: {
          source_url: MEDIA_URL,
          alt: 'Children painting',
          logo: false,
          copyright_notice: 'Copied from the provider website.',
        },
      }),
      proposal({}),
    ]);

    const previews = screen.getAllByRole('img', { name: 'Children painting' });
    expect(previews).toHaveLength(2);
    for (const preview of previews) {
      expect(preview).toHaveAttribute('src', MEDIA_URL);
    }
    expect(screen.getAllByText('Children painting').length).toBeGreaterThan(0);
    expect(screen.queryByText(MEDIA_URL)).not.toBeInTheDocument();
    expect(screen.queryByText(/source_url/)).not.toBeInTheDocument();
    expect(screen.queryByText(/logo:/)).not.toBeInTheDocument();
    expect(screen.getAllByText('Now: Empty').length).toBeGreaterThan(0);
    expect(
      screen.getAllByText('description: Saturday classes for children.').length
    ).toBeGreaterThan(0);
  });

  it('keeps a non-http source as text and does not request it', () => {
    renderTable([
      proposal({
        id: 'prop-bad',
        section: 'Media',
        kind: 'add_media',
        field: 'media',
        label: 'Photo 1',
        proposed_value: { source_url: 'javascript:alert(1)' },
      }),
    ]);

    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getAllByText('source_url: javascript:alert(1)').length).toBeGreaterThan(
      0
    );
  });

  it('says the preview is unavailable when the image fails, without the URL', () => {
    renderTable([
      proposal({
        id: 'prop-media',
        section: 'Media',
        kind: 'add_media',
        field: 'logo',
        label: 'Logo',
        proposed_value: { source_url: MEDIA_URL, alt: MEDIA_URL, logo: true },
      }),
    ]);

    for (const preview of screen.getAllByTestId('enrichment-media-preview')) {
      fireEvent.error(preview);
    }

    expect(screen.getAllByText('Preview unavailable')).toHaveLength(2);
    expect(screen.queryByTestId('enrichment-media-preview')).not.toBeInTheDocument();
    expect(screen.queryByText(MEDIA_URL)).not.toBeInTheDocument();
    expect(screen.queryByRole('img', { name: MEDIA_URL })).not.toBeInTheDocument();
  });
});
