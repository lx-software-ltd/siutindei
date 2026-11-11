import type { ActivityListing, ActivityListingVariant } from './types';

function variantKey(variant: ActivityListingVariant): string {
  return JSON.stringify([
    variant.location.id,
    variant.pricing,
    variant.schedule?.weeklyEntries ?? null,
  ]);
}

/**
 * Search returns one row per activity, venue, price, and schedule. Merge the
 * rows of one activity into a single listing, keeping first-seen order. The
 * first row stays the listing's own location, pricing, and schedule.
 */
export function groupListings(
  items: readonly ActivityListing[],
): readonly ActivityListing[] {
  const order: string[] = [];
  const firsts = new Map<string, ActivityListing>();
  const variants = new Map<string, ActivityListingVariant[]>();
  const seen = new Map<string, Set<string>>();

  for (const item of items) {
    const id = item.activity.id;
    if (!firsts.has(id)) {
      order.push(id);
      firsts.set(id, item);
      variants.set(id, []);
      seen.set(id, new Set());
    }
    const rows = item.variants ?? [item];
    for (const row of rows) {
      const variant: ActivityListingVariant = {
        location: row.location,
        pricing: row.pricing,
        schedule: row.schedule,
      };
      const key = variantKey(variant);
      const keys = seen.get(id);
      if (keys && !keys.has(key)) {
        keys.add(key);
        variants.get(id)?.push(variant);
      }
    }
  }

  return order.map((id) => {
    const first = firsts.get(id) as ActivityListing;
    return { ...first, variants: variants.get(id) ?? [] };
  });
}

export function listingVariants(
  listing: ActivityListing,
): readonly ActivityListingVariant[] {
  if (listing.variants && listing.variants.length > 0) {
    return listing.variants;
  }
  return [
    {
      location: listing.location,
      pricing: listing.pricing,
      schedule: listing.schedule,
    },
  ];
}

/** Distinct venues of a listing, in first-seen order. */
export function listingVenues(
  listing: ActivityListing,
): readonly ActivityListingVariant[] {
  const byLocation = new Map<string, ActivityListingVariant>();
  for (const variant of listingVariants(listing)) {
    if (!byLocation.has(variant.location.id)) {
      byLocation.set(variant.location.id, variant);
    }
  }
  return [...byLocation.values()];
}
