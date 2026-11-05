'use client';

import type { ReactNode } from 'react';

import { locationDisplayName } from '../../lib/location-label';
import type { CatalogVersionView } from '../admin/version-history';
import { VersionField, VersionFields, VersionSwitcher } from '../admin/version-history';
import { StatusBanner } from '../status-banner';
import { Button } from '../ui/button';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { Select } from '../ui/select';

interface LocationChoice {
  id: string;
  name?: string | null;
  address?: string | null;
  area_id?: string | null;
}

interface ActivityChoice {
  id: string;
  name?: string | null;
}

/**
 * Expanded pricing or schedule row: version chrome plus the shared
 * location and activity selects. Domain fields are `children`.
 */
export function CatalogInlineEditor({
  idPrefix,
  view,
  editingId,
  error,
  isHistorical,
  onBackToLatest,
  editorMode,
  onSubmit,
  isSaving,
  locations,
  activities,
  locationId,
  activityId,
  locked,
  showLocationError,
  showActivityError,
  locationError,
  activityError,
  errorClassName,
  onLocationChange,
  onActivityChange,
  children,
}: {
  idPrefix: string;
  view: CatalogVersionView;
  editingId: string | null;
  error: string;
  isHistorical: boolean;
  onBackToLatest: () => void;
  editorMode: 'create' | 'edit';
  onSubmit: () => void;
  isSaving: boolean;
  locations: readonly LocationChoice[];
  activities: readonly ActivityChoice[];
  locationId: string;
  activityId: string;
  locked: boolean;
  showLocationError: boolean;
  showActivityError: boolean;
  locationError: string;
  activityError: string;
  errorClassName: string;
  onLocationChange: (value: string) => void;
  onActivityChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <AdminEditorPanel
      accessory={editingId ? <VersionSwitcher view={view} /> : undefined}
      status={error ? <StatusBanner kind='error'>{error}</StatusBanner> : null}
      actions={
        isHistorical ? (
          <Button type='button' variant='secondary' onClick={onBackToLatest}>
            Back to latest
          </Button>
        ) : (
          <AdminEditorActions mode={editorMode} onSubmit={onSubmit} isSaving={isSaving} />
        )
      }
    >
      <VersionFields view={view}>
        <div className='space-y-4'>
          <AdminFieldGrid columns={2}>
            <VersionField
              label='Location'
              htmlFor={`${idPrefix}-location`}
              required
              versionKey='location_id'
              error={showLocationError ? locationError : undefined}
            >
              <Select
                id={`${idPrefix}-location`}
                value={locationId}
                disabled={locked}
                onChange={(event) => onLocationChange(event.target.value)}
                className={showLocationError ? errorClassName : ''}
                aria-invalid={showLocationError || undefined}
              >
                <option value=''>Select location</option>
                {locations.map((location) => (
                  <option key={location.id} value={location.id}>
                    {locationDisplayName(location, location.area_id ?? '')}
                  </option>
                ))}
              </Select>
            </VersionField>
            <VersionField
              label='Activity'
              htmlFor={`${idPrefix}-activity`}
              required
              versionKey='activity_id'
              error={showActivityError ? activityError : undefined}
            >
              <Select
                id={`${idPrefix}-activity`}
                value={activityId}
                disabled={locked}
                onChange={(event) => onActivityChange(event.target.value)}
                className={showActivityError ? errorClassName : ''}
                aria-invalid={showActivityError || undefined}
              >
                <option value=''>Select activity</option>
                {activities.map((activity) => (
                  <option key={activity.id} value={activity.id}>
                    {activity.name}
                  </option>
                ))}
              </Select>
            </VersionField>
            {children}
          </AdminFieldGrid>
        </div>
      </VersionFields>
    </AdminEditorPanel>
  );
}
