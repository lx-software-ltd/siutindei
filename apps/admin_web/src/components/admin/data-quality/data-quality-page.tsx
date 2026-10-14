'use client';

import { useQueryState } from 'nuqs';

import { adminTabLabel } from '../../../lib/admin-page-name';
import { AdminTabStrip } from '../../ui/admin-tab-strip';
import { CategoryChecksPanel } from '../category-suggestions/category-checks-panel';
import { DeletedPanel } from './deleted-panel';
import { DuplicatesPanel } from './duplicates-panel';
import { LocationsPanel } from './locations-panel';
import { NamesPanel } from './names-panel';
import { RunsPanel } from './runs-panel';

const TABS = [
  { key: 'duplicates', label: adminTabLabel.duplicates },
  { key: 'names', label: adminTabLabel.names },
  { key: 'locations', label: adminTabLabel.locations },
  { key: 'checks', label: adminTabLabel.categories },
  { key: 'runs', label: adminTabLabel.runs },
  { key: 'deleted', label: adminTabLabel.deleted },
] as const;

export function DataQualityPage() {
  const [tabParam, setTabParam] = useQueryState('tab');
  const activeTab =
    tabParam === 'names' ||
    tabParam === 'locations' ||
    tabParam === 'checks' ||
    tabParam === 'runs' ||
    tabParam === 'deleted'
      ? tabParam
      : 'duplicates';

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
      ) : activeTab === 'locations' ? (
        <LocationsPanel />
      ) : activeTab === 'checks' ? (
        <CategoryChecksPanel />
      ) : activeTab === 'runs' ? (
        <RunsPanel />
      ) : activeTab === 'deleted' ? (
        <DeletedPanel />
      ) : (
        <DuplicatesPanel />
      )}
    </div>
  );
}
