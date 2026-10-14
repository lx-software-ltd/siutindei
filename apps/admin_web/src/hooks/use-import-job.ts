'use client';

import { useQuery } from '@tanstack/react-query';

import { adminQueryKeys } from '@/lib/admin-query-keys';
import { getCategorySuggestion } from '@/lib/api-client-category-suggestions';
import { getAdminImportJob } from '@/lib/api-client-imports';
import { capturedCategoryLabel } from '@/lib/import-job-results';

const SETTLED_STALE_MS = 30 * 60 * 1000;
const RUNNING_REFRESH_MS = 5_000;

export function useImportJob(jobId: string, status?: string) {
  const running = status === 'running';
  return useQuery({
    queryKey: adminQueryKeys.importJob(jobId),
    queryFn: () => getAdminImportJob(jobId),
    staleTime: running ? 0 : SETTLED_STALE_MS,
    refetchInterval: running ? RUNNING_REFRESH_MS : false,
    refetchOnWindowFocus: running,
  });
}

export function useCapturedCategoryNames(jobId: string, ids: readonly string[]) {
  return useQuery({
    queryKey: [...adminQueryKeys.importJob(jobId), 'category-names', ids],
    queryFn: async () => {
      const names: string[] = [];
      let unavailable = 0;
      await Promise.all(
        ids.map(async (id) => {
          try {
            const suggestion = await getCategorySuggestion(id);
            const label = capturedCategoryLabel(suggestion);
            if (label) {
              names.push(label);
            } else {
              unavailable += 1;
            }
          } catch {
            unavailable += 1;
          }
        })
      );
      return { names, unavailable };
    },
    enabled: ids.length > 0,
    staleTime: SETTLED_STALE_MS,
    refetchOnWindowFocus: false,
  });
}
