import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import {
  ProposalTable,
  areaIdFromPath,
  matchedAreaId,
  selectionAfterToggle,
} from '@/components/admin/organization-enrichment-proposals';
import type { EnrichmentProposal } from '@/lib/api-client-enrichment';
import type { GeographicAreaNode } from '@/lib/api-client-user';

const areaState = vi.hoisted(() => ({
  tree: [] as GeographicAreaNode[],
}));

vi.mock('@/hooks/use-activity-categories', () => ({
  useActivityCategories: () => ({
    tree: [],
    isLoading: false,
    flatNodes: () => [],
  }),
}));

vi.mock('@/hooks/use-geographic-areas', () => ({
  useGeographicAreas: () => ({
    tree: areaState.tree,
    isLoading: false,
    countryCodes: '',
    flatNodes: () => [],
  }),
}));

const HONG_KONG: GeographicAreaNode = {
  id: 'area-hk',
  parent_id: null,
  name: 'Hong Kong',
  name_translations: {},
  level: 'country',
  code: 'HK',
  active: true,
  display_order: 1,
  children: [
    {
      id: 'area-hk-island',
      parent_id: 'area-hk',
      name: 'Hong Kong Island',
      name_translations: { 'zh-HK': '香港島' },
      level: 'region',
      code: null,
      active: true,
      display_order: 1,
      children: [
        {
          id: 'area-hk-wanchai',
          parent_id: 'area-hk-island',
          name: 'Wan Chai',
          name_translations: {},
          level: 'district',
          code: null,
          active: true,
          display_order: 1,
          children: [
            {
              id: 'area-hk-causeway',
              parent_id: 'area-hk-wanchai',
              name: 'Causeway Bay',
              name_translations: {},
              level: 'neighbourhood',
              code: null,
              active: true,
              display_order: 1,
              children: [],
            },
          ],
        },
      ],
    },
  ],
};

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

describe('matched area selection', () => {
  it('selects the region from a path that has no neighbourhood id', () => {
    expect(areaIdFromPath([HONG_KONG], 'Hong Kong Island · Wan Chai')).toBe(
      'area-hk-wanchai'
    );
    expect(
      matchedAreaId(
        { area_path: 'Hong Kong Island · Wan Chai' },
        [HONG_KONG]
      )
    ).toBe('area-hk-wanchai');
    expect(
      matchedAreaId(
        { area_path: '香港島' },
        [HONG_KONG]
      )
    ).toBe('area-hk-island');
  });

  it('shows the region selected on the location proposal', () => {
    areaState.tree = [HONG_KONG];
    renderTable([
      proposal({
        id: 'prop-location',
        section: 'Locations',
        kind: 'create_location',
        field: null,
        label: 'Location · 1 Test Street',
        proposed_value: {
          address: '1 Test Street',
          area_path: 'Hong Kong Island · Wan Chai',
        },
      }),
    ]);
    expect(screen.getByLabelText('Region')).toHaveValue('area-hk-island');
    expect(screen.getByLabelText('District')).toHaveValue('area-hk-wanchai');
    areaState.tree = [];
  });
});

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
