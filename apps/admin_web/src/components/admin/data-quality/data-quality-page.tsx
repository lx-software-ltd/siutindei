'use client';

import { useQueryState } from 'nuqs';

import { AdminTabStrip } from '../../ui/admin-tab-strip';
import { CategoryChecksPanel } from '../category-suggestions/category-checks-panel';
import { DuplicatesPanel } from './duplicates-panel';
import { NamesPanel } from './names-panel';

const TABS = [
  { key: 'duplicates', label: 'Duplicates' },
  { key: 'names', label: 'Names' },
  { key: 'checks', label: 'Category' },
] as const;

export function DataQualityPage() {
  const [tabParam, setTabParam] = useQueryState('tab');
  const activeTab =
    tabParam === 'names' || tabParam === 'checks' ? tabParam : 'duplicates';

  return (
    <div className='space-y-4'>
      <AdminTabStrip
        aria-label='Data quality'
        items={TABS}
        activeKey={activeTab}
        onChange={(key) => {
          void setTabParam(key === 'duplicates' ? null : key);
        }}
      />
      {activeTab === 'names' ? (
        <NamesPanel />
      ) : activeTab === 'checks' ? (
        <CategoryChecksPanel />
      ) : (
        <DuplicatesPanel />
      )}
    </div>
  );
}
