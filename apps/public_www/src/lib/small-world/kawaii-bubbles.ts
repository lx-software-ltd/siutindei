export const BUBBLE_IDS = [
  'junk',
  'tram',
  'longevity',
  'vase',
  'balloon',
  'clock-tower',
  'fan',
  'bauhinia',
  'incense',
  'lantern',
  'teacup',
  'bao',
  'steamer',
  'bamboo',
  'teapot',
  'fish-balls',
  'bowl',
  'yin-yang',
  'noodles',
  'parasol',
] as const;

export type BubbleId = (typeof BUBBLE_IDS)[number];

export interface BubbleSlot {
  readonly className: string;
  readonly largeOnly: boolean;
}

export const BUBBLE_SLOTS: readonly BubbleSlot[] = [
  {
    className:
      'left-[3%] top-[10%] w-20 md:left-[5%] md:w-28',
    largeOnly: false,
  },
  {
    className:
      'right-[3%] top-[16%] w-24 md:right-[6%] md:w-36',
    largeOnly: false,
  },
  {
    className:
      'bottom-[8%] left-[8%] w-16 md:left-[12%] md:w-24',
    largeOnly: false,
  },
  {
    className:
      'right-[5%] top-1/2 w-20 -translate-y-1/2 md:right-[8%] md:w-28',
    largeOnly: true,
  },
  {
    className:
      'left-[10%] top-[42%] w-16 md:left-[14%] md:w-24',
    largeOnly: true,
  },
  {
    className:
      'right-[10%] bottom-[12%] w-16 md:right-[14%] md:w-24',
    largeOnly: true,
  },
];

/** Freed for the scope plates, which sit in that corner. */
export const TOP_RIGHT_BUBBLE_SLOT = 1;

export const LARGE_BUBBLE_COUNT = 6;
export const SMALL_BUBBLE_COUNT = 3;

export function bubbleSrc(id: BubbleId): string {
  return `/images/small-world/bubble-${id}.webp`;
}

function shuffleIds(
  ids: readonly BubbleId[],
  random: () => number = Math.random,
): BubbleId[] {
  const next = [...ids];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    const current = next[index];
    const other = next[swap];
    if (current === undefined || other === undefined) {
      continue;
    }
    next[index] = other;
    next[swap] = current;
  }
  return next;
}

/** Stable seed so the hero bubbles are in the static HTML and match hydration. */
export const BUBBLE_BUILD_SEED = 20261102;

function mulberry32(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let value = state;
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

export function pickBubbleIdsForSeed(
  seed: number,
  count: number = LARGE_BUBBLE_COUNT,
): BubbleId[] {
  return pickBubbleIds(count, mulberry32(seed));
}

export function pickBubbleIds(
  count: number = LARGE_BUBBLE_COUNT,
  random: () => number = Math.random,
): BubbleId[] {
  return shuffleIds(BUBBLE_IDS, random).slice(0, count);
}
