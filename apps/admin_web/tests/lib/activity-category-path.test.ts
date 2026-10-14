import { describe, expect, it } from 'vitest';

import {
  flattenCategoriesByPathOrder,
  groupCategoriesByParent,
  type CategoryPathNode,
} from '@/lib/activity-category-path';

function category(
  id: string,
  name: string,
  displayOrder: number,
  parentId: string | null = null
): CategoryPathNode {
  return {
    id,
    name,
    display_order: displayOrder,
    parent_id: parentId,
  };
}

describe('flattenCategoriesByPathOrder', () => {
  it('places children between a parent and the next sibling', () => {
    const a1 = category('a-1', 'A', 1);
    const a2 = category('a-2', 'A', 2);
    const aa1 = category('a-a-1', 'A', 1, 'a-1');

    expect(flattenCategoriesByPathOrder([a2, aa1, a1])).toEqual([
      a1,
      aa1,
      a2,
    ]);
  });

  it('walks each path level by display_order then name', () => {
    const sport = category('sport', 'Sport', 1);
    const arts = category('arts', 'Arts', 2);
    const water = category('water', 'Water Sports', 1, 'sport');
    const team = category('team', 'Team Sports', 2, 'sport');
    const paint = category('paint', 'Painting', 1, 'arts');

    const shuffled = [paint, team, sport, arts, water];

    expect(flattenCategoriesByPathOrder(shuffled).map((item) => item.id)).toEqual(
      ['sport', 'water', 'team', 'arts', 'paint']
    );
  });

  it('treats a missing parent as a root', () => {
    const orphan = category('orphan', 'Orphan', 0, 'missing-parent');
    const root = category('root', 'Root', 1);

    expect(flattenCategoriesByPathOrder([orphan, root]).map((item) => item.id)).toEqual(
      ['orphan', 'root']
    );
  });

  it('breaks remaining ties by id', () => {
    const first = category('aaa', 'Shared', 1);
    const second = category('zzz', 'Shared', 1);

    expect(flattenCategoriesByPathOrder([second, first]).map((item) => item.id)).toEqual(
      ['aaa', 'zzz']
    );
  });
});

describe('groupCategoriesByParent', () => {
  it('sorts siblings under each parent', () => {
    const parent = category('parent', 'Parent', 1);
    const later = category('later', 'Later', 2, 'parent');
    const earlier = category('earlier', 'Earlier', 1, 'parent');

    const grouped = groupCategoriesByParent([later, parent, earlier]);

    expect(grouped.get('')?.map((item) => item.id)).toEqual(['parent']);
    expect(grouped.get('parent')?.map((item) => item.id)).toEqual([
      'earlier',
      'later',
    ]);
  });
});
