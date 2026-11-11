import { Skeleton } from '@/components/shared/ui/skeleton';

export function ListingCardSkeleton({
  layout = 'carousel',
}: {
  readonly layout?: 'carousel' | 'grid';
}) {
  if (layout === 'grid') {
    return (
      <div className="listing-card flex w-full gap-3 sm:block" aria-hidden="true">
        <Skeleton className="aspect-square w-28 shrink-0 sm:aspect-[4/3] sm:w-full" />
        <div className="min-w-0 flex-1 sm:mt-3">
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="mt-2 h-3 w-3/5" />
          <Skeleton className="mt-2 h-3 w-2/5" />
        </div>
      </div>
    );
  }
  return (
    <div className="listing-card w-[280px] shrink-0 sm:w-[300px]" aria-hidden="true">
      <Skeleton className="aspect-[4/3] w-full" />
      <Skeleton className="mt-3 h-4 w-4/5" />
      <Skeleton className="mt-2 h-3 w-3/5" />
      <Skeleton className="mt-2 h-3 w-2/5" />
    </div>
  );
}
