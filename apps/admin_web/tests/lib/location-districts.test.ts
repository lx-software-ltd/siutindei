import { describe, expect, it } from 'vitest';

import {
  areaAncestry,
  districtKey,
  pinIsOutside,
  pinOutsideDistrict,
  type DistrictArea,
} from '@/lib/location-districts';

const hongKong: DistrictArea = {
  id: 'hk',
  name: 'Hong Kong',
  code: 'HK',
  children: [],
};

const wanChai: DistrictArea = {
  id: 'wan-chai',
  name: '灣仔',
  children: [],
};

describe('pinIsOutside', () => {
  it('flags a Central pin in Sham Shui Po and a pin outside Hong Kong', () => {
    expect(pinIsOutside(22.28, 114.15, 'sham-shui-po')).toBe(true);
    expect(pinIsOutside(22.28, 114.15, 'central-and-western')).toBe(false);
    expect(pinIsOutside(0, 0, 'central-and-western')).toBe(true);
  });

  it('keeps a pin on a shared boundary inside both districts', () => {
    expect(pinIsOutside(22.3245, 114.1685, 'yau-tsim-mong')).toBe(false);
    expect(pinIsOutside(22.3245, 114.1685, 'sham-shui-po')).toBe(false);
    expect(pinIsOutside(22.265, 114.237, 'eastern')).toBe(false);
    expect(pinIsOutside(22.265, 114.237, 'southern')).toBe(false);
  });

  it('ignores a gap inside Hong Kong', () => {
    expect(pinIsOutside(22.2, 114.175, 'wan-chai')).toBe(false);
  });
});

describe('districtKey', () => {
  it('requires Hong Kong before an alias matches', () => {
    const island: DistrictArea = {
      id: 'island',
      name: 'Hong Kong Island',
      children: [],
    };
    expect(districtKey([wanChai, island])).toBeNull();
    expect(districtKey([wanChai, island, hongKong])).toBe('wan-chai');
    const singapore: DistrictArea = {
      id: 'sg',
      name: 'Singapore',
      code: 'SG',
      children: [],
    };
    const north: DistrictArea = { id: 'north', name: 'North', children: [] };
    expect(districtKey([north, singapore])).toBeNull();
  });
});

describe('pinOutsideDistrict', () => {
  const tree: DistrictArea[] = [
    {
      ...hongKong,
      children: [
        {
          id: 'island',
          name: 'Hong Kong Island',
          children: [
            {
              ...wanChai,
              children: [
                {
                  id: 'centre',
                  name: 'Wan Chai',
                  children: [],
                },
              ],
            },
          ],
        },
      ],
    },
  ];

  it('warns when the selected district does not contain the pin', () => {
    const areas = areaAncestry(tree, 'centre');
    expect(areas.map((area) => area.id)).toEqual([
      'centre',
      'wan-chai',
      'island',
      'hk',
    ]);
    expect(pinOutsideDistrict(22.278, 114.175, areas)).toBe(false);
    expect(pinOutsideDistrict(22.5, 114.175, areas)).toBe(true);
    expect(pinOutsideDistrict(22.278, 114.175, [])).toBe(false);
  });
});
