import {
  decideCategoryReviewsBulk,
  type CategoryReviewBulkBody,
  type CategoryReviewBulkResult,
} from '../../../lib/api-client-category-suggestions';

const PENDING_CATEGORY_ID = 'c1111111-1111-1111-1111-111111111199';
const MAX_PAGES = 80;
const MAX_FAILURES = 20;

export interface BulkProgress {
  decided: number;
  skipped: number;
  failed: number;
  matched: number;
}

export interface BulkOutcome extends BulkProgress {
  failures: Array<{ id: string; message: string }>;
  applicable: number;
  cancelled: boolean;
  truncated: boolean;
}

export function canApplyReview(item: {
  proposed_category_id?: string | null;
  verdict: string;
  current_category_id?: string | null;
}): boolean {
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
  filters: Omit<CategoryReviewBulkBody, 'action' | 'dry_run' | 'cursor'>,
  action: 'apply' | 'dismiss',
  options?: {
    signal?: AbortSignal;
    onProgress?: (progress: BulkProgress) => void;
  }
): Promise<BulkOutcome> {
  const signal = options?.signal;
  const preview = await decideCategoryReviewsBulk(
    { ...filters, action, dry_run: true },
    signal
  );
  let decided = 0;
  let skipped = 0;
  let failed = 0;
  const failures: BulkOutcome['failures'] = [];
  let cursor: string | undefined;
  const report = () => {
    options?.onProgress?.({
      decided,
      skipped,
      failed,
      matched: preview.matched,
    });
  };
  try {
    for (let page = 0; page < MAX_PAGES; page += 1) {
      if (signal?.aborted) {
        return outcome(preview, decided, skipped, failed, failures, true, false);
      }
      const result: CategoryReviewBulkResult = await decideCategoryReviewsBulk(
        { ...filters, action, cursor },
        signal
      );
      decided += result.decided;
      skipped += result.skipped;
      failed += result.failed;
      for (const item of result.failures) {
        if (failures.length < MAX_FAILURES) {
          failures.push(item);
        }
      }
      report();
      if (!result.next_cursor) {
        return outcome(preview, decided, skipped, failed, failures, false, false);
      }
      cursor = result.next_cursor;
    }
  } catch (err) {
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      return outcome(preview, decided, skipped, failed, failures, true, false);
    }
    throw err;
  }
  return outcome(preview, decided, skipped, failed, failures, false, true);
}

function outcome(
  preview: CategoryReviewBulkResult,
  decided: number,
  skipped: number,
  failed: number,
  failures: BulkOutcome['failures'],
  cancelled: boolean,
  truncated: boolean
): BulkOutcome {
  return {
    decided,
    skipped,
    failed,
    failures,
    matched: preview.matched,
    applicable: preview.applicable,
    cancelled,
    truncated,
  };
}
