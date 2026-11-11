import { describe, expect, it } from 'vitest';

import { scopeArrow } from '@/lib/small-world/scope-arrow';

const desktop = {
  word: { left: 656, top: 404, right: 751, bottom: 428 },
  sign: { left: 1106, top: 22, right: 1248, bottom: 106 },
  headingRight: 972,
  headingBottom: 358,
  width: 1280,
};

describe('scopeArrow', () => {
  it('runs from the struck word, past the heading, to just under the plate', () => {
    const arrow = scopeArrow(desktop);
    expect(arrow).not.toBeNull();
    if (!arrow) {
      return;
    }
    expect(arrow.start.x).toBeGreaterThan(desktop.word.left);
    expect(arrow.start.x).toBeLessThan(desktop.word.right);
    expect(arrow.start.y).toBeLessThanOrEqual(desktop.word.top);
    expect(arrow.end.x).toBeGreaterThan(desktop.sign.left);
    expect(arrow.end.x).toBeLessThan(desktop.sign.right);
    expect(arrow.end.y).toBeGreaterThan(desktop.sign.bottom);
    expect(arrow.corner.x).toBeGreaterThan(desktop.headingRight);
    expect(arrow.corner.x).toBeLessThan(desktop.width);
    expect(arrow.head[1]).toEqual(arrow.end);
    for (const point of [arrow.start, arrow.corner, arrow.end]) {
      expect(point.x).toBeGreaterThan(0);
      expect(point.x).toBeLessThan(desktop.width);
    }
  });

  it('returns nothing when a box has no size', () => {
    expect(
      scopeArrow({
        ...desktop,
        word: { left: 0, top: 0, right: 0, bottom: 0 },
      }),
    ).toBeNull();
    expect(scopeArrow({ ...desktop, width: 0 })).toBeNull();
  });
});
