/** Matches `MAX_LISTING_AGE` in `backend/src/app/db/age_bounds.py`. */
export const MAX_LISTING_AGE = 18;

export function capListingAge(
  ageMin: number,
  ageMax: number
): { ageMin: number; ageMax: number } {
  return {
    ageMin: Math.min(ageMin, MAX_LISTING_AGE),
    ageMax: Math.min(ageMax, MAX_LISTING_AGE),
  };
}
