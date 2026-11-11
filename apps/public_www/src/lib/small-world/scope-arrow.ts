export interface ArrowPoint {
  readonly x: number;
  readonly y: number;
}

export interface ArrowBox {
  readonly left: number;
  readonly top: number;
  readonly right: number;
  readonly bottom: number;
}

export interface ScopeArrow {
  readonly start: ArrowPoint;
  readonly corner: ArrowPoint;
  readonly end: ArrowPoint;
  readonly startControls: readonly [ArrowPoint, ArrowPoint];
  readonly endControls: readonly [ArrowPoint, ArrowPoint];
  readonly head: readonly [ArrowPoint, ArrowPoint, ArrowPoint];
}

const HEAD_LENGTH = 16;
const HEAD_SPREAD = 0.5;

function arrowHead(
  from: ArrowPoint,
  to: ArrowPoint,
): readonly [ArrowPoint, ArrowPoint, ArrowPoint] {
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  return [
    {
      x: to.x - HEAD_LENGTH * Math.cos(angle - HEAD_SPREAD),
      y: to.y - HEAD_LENGTH * Math.sin(angle - HEAD_SPREAD),
    },
    to,
    {
      x: to.x - HEAD_LENGTH * Math.cos(angle + HEAD_SPREAD),
      y: to.y - HEAD_LENGTH * Math.sin(angle + HEAD_SPREAD),
    },
  ];
}

/**
 * A curve from the struck words, under the heading, up to the lowest plate.
 * Coordinates are hero-relative. Phones use a fixed arrow picture instead.
 */
export function scopeArrow(input: {
  readonly word: ArrowBox;
  readonly sign: ArrowBox;
  readonly headingRight: number;
  readonly headingBottom: number;
  readonly width: number;
}): ScopeArrow | null {
  const { word, sign, width } = input;
  if (word.right <= word.left || sign.bottom <= sign.top || width <= 0) {
    return null;
  }
  const start = {
    x: word.left + (word.right - word.left) * 0.55,
    y: word.top - 2,
  };
  const end = {
    x: Math.min(sign.right - 20, width - 16),
    y: sign.bottom + 12,
  };
  // Travel in the gap under the heading, then rise on its right.
  const travelY = Math.min(input.headingBottom + 8, start.y - 6);
  const riseX = Math.min(
    Math.max(input.headingRight + 28, end.x),
    width - 16,
  );
  const corner = { x: riseX, y: travelY };
  const startControls: [ArrowPoint, ArrowPoint] = [
    { x: start.x, y: travelY },
    { x: start.x + (riseX - start.x) * 0.2, y: travelY },
  ];
  const endControls: [ArrowPoint, ArrowPoint] = [
    { x: riseX, y: travelY - 12 },
    { x: end.x, y: end.y + (travelY - end.y) * 0.4 },
  ];
  return {
    start,
    corner,
    end,
    startControls,
    endControls,
    head: arrowHead(endControls[1], end),
  };
}
