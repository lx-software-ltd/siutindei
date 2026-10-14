'use client';

import { useQuery } from '@tanstack/react-query';

import { adminQueryKeys } from '../../lib/admin-query-keys';
import { getDataQualityRun } from '../../lib/api-client-data-quality';
import { runStatusLabel } from './data-quality/runs-panel';

const SETTLED = new Set(['done', 'partial', 'failed', 'busy']);

export function ImportRunStatus({ runId }: { runId: string }) {
  const query = useQuery({
    queryKey: [...adminQueryKeys.dataQualityRun(runId), 'status'],
    queryFn: () => getDataQualityRun(runId, 'status'),
    refetchInterval: (current) =>
      SETTLED.has(current.state.data?.status ?? '') ? false : 3000,
  });
  const run = query.data;
  return (
    <p>
      Data quality:{' '}
      <a
        className='underline underline-offset-2'
        href={`/admin/dashboard?section=data-quality&tab=runs&run=${encodeURIComponent(runId)}`}
      >
        {run ? runStatusLabel(run) : 'Queued'}
      </a>
    </p>
  );
}
