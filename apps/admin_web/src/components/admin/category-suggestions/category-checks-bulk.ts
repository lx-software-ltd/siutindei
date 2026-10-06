import {
  decideCategoryReview,
  listCategoryReviews,
  type ActivityCategoryReview,
  type CategoryReviewFilters,
} from '../../../lib/api-client-category-suggestions';

const PENDING_CATEGORY_ID = 'c1111111-1111-1111-1111-111111111199';
const PAGE_LIMIT = 100;
const MAX_PAGES = 40;

export function canApplyReview(item: ActivityCategoryReview): boolean {
  if (item.proposed_category_id) {
    return true;
  }
  return (
    item.verdict === 'confirm' &&
    Boolean(item.current_category_id) &&
    item.current_category_id !== PENDING_CATEGORY_ID
  );
}

export async function decideMatchingPending(
  filters: Omit<CategoryReviewFilters, 'status' | 'cursor' | 'limit'>,
  action: 'apply' | 'dismiss'
): Promise<{ decided: number; skipped: number; failed: number }> {
  const seen = new Set<string>();
  let decided = 0;
  let skipped = 0;
  let failed = 0;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const result = await listCategoryReviews({
      ...filters,
      status: 'pending',
      limit: PAGE_LIMIT,
    });
    const fresh = result.items.filter((item) => !seen.has(item.id));
    if (fresh.length === 0) {
      break;
    }
    for (const item of fresh) {
      seen.add(item.id);
      if (item.status !== 'pending') {
        skipped += 1;
        continue;
      }
      if (action === 'apply' && !canApplyReview(item)) {
        skipped += 1;
        continue;
      }
      try {
        await decideCategoryReview(item.id, { action });
        decided += 1;
      } catch {
        failed += 1;
      }
    }
  }
  return { decided, skipped, failed };
}
