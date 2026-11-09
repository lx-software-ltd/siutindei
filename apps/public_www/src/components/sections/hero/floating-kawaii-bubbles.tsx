import type { SiteContent } from '@/content/types';
import {
  BUBBLE_SLOTS,
  type BubbleId,
  bubbleSrc,
} from '@/lib/small-world/kawaii-bubbles';

const DRIFT = [
  'small-world-bubble--drift-a',
  'small-world-bubble--drift-b',
  'small-world-bubble--drift-c',
] as const;

interface FloatingKawaiiBubblesProps {
  readonly copy: SiteContent['smallWorld'];
  readonly ids: readonly BubbleId[];
}

export function FloatingKawaiiBubbles({
  copy,
  ids,
}: FloatingKawaiiBubblesProps) {
  return (
    <div
      className="pointer-events-none absolute inset-0"
      aria-label={copy.sceneAriaLabel}
    >
      {ids.map((id, index) => {
        const slot = BUBBLE_SLOTS[index];
        if (!slot) {
          return null;
        }
        const drift = DRIFT[index % DRIFT.length];
        const largeOnly = slot.largeOnly ? 'max-lg:hidden' : '';
        // Decorative. fetchPriority low stops React from hoisting these
        // into high-priority preloads ahead of the heading.
        return (
          <img
            key={id}
            src={bubbleSrc(id)}
            alt={copy.bubbles[id]}
            width={160}
            height={160}
            decoding="async"
            fetchPriority="low"
            className={`small-world-bubble ${drift} ${slot.className} ${largeOnly}`}
          />
        );
      })}
    </div>
  );
}
