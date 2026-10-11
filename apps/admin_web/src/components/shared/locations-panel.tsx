'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import type { GeographicAreaNode } from '../../lib/api-client';
import { parseOptionalNumber } from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import { normalizeKey } from '../../lib/string-utils';
import type { Location } from '../../types/admin';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import {
  AddressAutocomplete,
  type AddressSelection,
} from '../ui/address-autocomplete';
import { CascadingAreaSelect } from '../ui/cascading-area-select';
import { Input } from '../ui/input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { StatusBanner } from '../status-banner';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import { WorkspaceScopeGate } from '../admin/workspace-empty';

const MAP_ICON_BASE_URL =
  'https://api.iconify.design/simple-icons';

function buildMapIconUrl(slug: string, color: string): string {
  return `${MAP_ICON_BASE_URL}/${slug}.svg?color=%23${color}`;
}

const MAP_ICONS = {
  googleMaps: buildMapIconUrl('googlemaps', '4285F4'),
  appleMaps: buildMapIconUrl('apple', '000000'),
};

function MapServiceIcon({
  className,
  src,
}: {
  className?: string;
  src: string;
}) {
  return (
    <img
      className={className}
      src={src}
      alt=''
      aria-hidden='true'
      loading='lazy'
      width={16}
      height={16}
    />
  );
}

interface LocationFormState {
  org_id: string;
  area_id: string;
  address: string;
  lat: string;
  lng: string;
}

const emptyForm: LocationFormState = {
  org_id: '',
  area_id: '',
  address: '',
  lat: '',
  lng: '',
};

function itemToForm(item: Location): LocationFormState {
  return {
    org_id: item.org_id ?? '',
    area_id: item.area_id ?? '',
    address: item.address ?? '',
    lat: item.lat !== undefined && item.lat !== null ? `${item.lat}` : '',
    lng: item.lng !== undefined && item.lng !== null ? `${item.lng}` : '',
  };
}

function buildMapQuery(location: Location): string | null {
  const { address, lat, lng } = location;
  const hasCoords =
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lng);
  const trimmedAddress = address?.trim();
  const query = hasCoords ? `${lat},${lng}` : trimmedAddress ?? '';
  if (!query) {
    return null;
  }
  return encodeURIComponent(query);
}

function buildGoogleMapsUrl(location: Location): string | null {
  const encodedQuery = buildMapQuery(location);
  if (!encodedQuery) {
    return null;
  }
  const baseUrl = 'https://www.google.com/maps/search/?api=1&query=';
  return `${baseUrl}${encodedQuery}`;
}

function buildAppleMapsUrl(location: Location): string | null {
  const encodedQuery = buildMapQuery(location);
  if (!encodedQuery) {
    return null;
  }
  const baseUrl = 'https://maps.apple.com/?q=';
  return `${baseUrl}${encodedQuery}`;
}

interface LocationsPanelProps {
  mode: ApiMode;
}

export function LocationsPanel({ mode }: LocationsPanelProps) {
  const isAdmin = mode === 'admin';
  const scope = useOrganizationScope();
  const scopedOrgId = scope.orgId;
  const { tree, countryCodes, matchNominatimResult } = useGeographicAreas();
  const defaultOrgId = scopedOrgId ?? '';
  const resolvedEmptyForm = useMemo(
    () => ({ ...emptyForm, org_id: defaultOrgId }),
    [defaultOrgId]
  );
  const panel = useResourceEditor<Location, LocationFormState>({
    resource: 'locations',
    mode,
    emptyForm: resolvedEmptyForm,
    itemToForm,
    paramName: 'location',
    legacyParam: 'edit',
    listFilters: scopedOrgId ? { org_id: scopedOrgId } : {},
    enabled: Boolean(scopedOrgId),
    noun: 'location',
  });

  const areaNameById = useMemo(() => {
    const map = new Map<string, string>();
    function walkTree(nodes: GeographicAreaNode[], parent?: GeographicAreaNode) {
      for (const node of nodes) {
        const label =
          parent && parent.level === 'district'
            ? `${node.name}, ${parent.name}`
            : node.name;
        map.set(node.id, label);
        if (node.children) {
          walkTree(node.children, node);
        }
      }
    }
    walkTree(tree);
    return map;
  }, [tree]);

  const getAreaName = useCallback(
    (areaId?: string) =>
      (areaId ? areaNameById.get(areaId) : undefined) ?? '—',
    [areaNameById]
  );

  const [searchQuery, setSearchQuery] = useState('');
  useExhaustPages(Boolean(searchQuery.trim()), {
    hasMore: panel.hasMore,
    isLoading: panel.isLoading,
    isLoadingMore: panel.isLoadingMore,
    error: panel.listError,
    loadMore: panel.loadMore,
  });

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['org_id', 'area_id', 'address'],
    formKey
  );
  const errorInputClassName =
    formErrorClassName;
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  const { setFormState } = panel;

  useEffect(() => {
    if (!defaultOrgId || panel.formState.org_id) {
      return;
    }
    if (!panel.isDraftOpen && panel.editingId === null) {
      return;
    }
    setFormState((prev) =>
      prev.org_id ? prev : { ...prev, org_id: defaultOrgId }
    );
  }, [
    defaultOrgId,
    panel.editingId,
    panel.formState.org_id,
    panel.isDraftOpen,
    setFormState,
  ]);

  const handleAddressSelect = (selection: AddressSelection) => {
    const match = matchNominatimResult(selection.raw, {
      lat: selection.lat,
      lng: selection.lng,
    });
    panel.setFormState((prev) => ({
      ...prev,
      address: selection.displayName,
      lat: `${selection.lat}`,
      lng: `${selection.lng}`,
      area_id: match ? match.areaId : prev.area_id,
    }));
  };

  const handleAreaChange = (areaId: string, _chain: GeographicAreaNode[]) => {
    markTouched('area_id');
    panel.setFormState((prev) => ({ ...prev, area_id: areaId }));
  };

  const validate = () => {
    if (!panel.formState.org_id || !panel.formState.area_id) {
      return 'Organization and area are required.';
    }
    const normalizedAddress = normalizeKey(panel.formState.address);
    if (normalizedAddress) {
      const hasDuplicate = panel.items.some((item) => {
        if (!item.address) {
          return false;
        }
        if (panel.editingId && item.id === panel.editingId) {
          return false;
        }
        return (
          item.org_id === panel.formState.org_id &&
          normalizeKey(item.address) === normalizedAddress
        );
      });
      if (hasDuplicate) {
        return 'Location address must be unique within the organization.';
      }
    }
    return null;
  };

  const areaError = panel.formState.area_id ? '' : 'Select an area.';
  const addressError = useMemo(() => {
    const normalizedAddress = normalizeKey(panel.formState.address);
    if (!normalizedAddress || !panel.formState.org_id) {
      return '';
    }
    const hasDuplicate = panel.items.some((item) => {
      if (!item.address) {
        return false;
      }
      if (panel.editingId && item.id === panel.editingId) {
        return false;
      }
      return (
        item.org_id === panel.formState.org_id &&
        normalizeKey(item.address) === normalizedAddress
      );
    });
    if (hasDuplicate) {
      return 'Address already exists for this organization.';
    }
    return '';
  }, [
    panel.editingId,
    panel.formState.address,
    panel.formState.org_id,
    panel.items,
  ]);

  const formToPayload = (form: LocationFormState) => ({
    org_id: form.org_id,
    area_id: form.area_id,
    address: form.address.trim() || null,
    lat: parseOptionalNumber(form.lat),
    lng: parseOptionalNumber(form.lng),
  });

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  function renderAddressCell(item: Location) {
    const googleMapsUrl = buildGoogleMapsUrl(item);
    const appleMapsUrl = buildAppleMapsUrl(item);
    const hasMapLinks = googleMapsUrl || appleMapsUrl;
    return (
      <div className='flex items-center gap-2 text-slate-600'>
        <span>{item.address || '—'}</span>
        {hasMapLinks && (
          <span className='inline-flex items-center gap-2'>
            {googleMapsUrl && (
              <a
                href={googleMapsUrl}
                target='_blank'
                rel='noreferrer'
                title='Open in Google Maps'
                aria-label='Open in Google Maps'
                className='text-slate-500 hover:text-slate-900'
              >
                <MapServiceIcon
                  className='h-4 w-4'
                  src={MAP_ICONS.googleMaps}
                />
              </a>
            )}
            {appleMapsUrl && (
              <a
                href={appleMapsUrl}
                target='_blank'
                rel='noreferrer'
                title='Open in Apple Maps'
                aria-label='Open in Apple Maps'
                className='text-slate-500 hover:text-slate-900'
              >
                <MapServiceIcon
                  className='h-4 w-4'
                  src={MAP_ICONS.appleMaps}
                />
              </a>
            )}
          </span>
        )}
      </div>
    );
  }

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const areaName = getAreaName(item.area_id).toLowerCase();
    return (
      areaName.includes(query) ||
      item.address?.toLowerCase().includes(query)
    );
  });

  const showAreaError = shouldShowError('area_id', areaError);
  const showAddressError = shouldShowError('address', addressError);
  const addressColumnPriority = 'secondary' as const;

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner kind='error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        <AdminEditorActions
          mode={panel.editorMode}
          onSubmit={handleSubmit}
          isSaving={panel.isSaving}
        />
      }
    >
      <AdminFieldGrid columns={2}>
        <AdminField
          label='Address'
          htmlFor='location-address'
          span={2}
          error={showAddressError ? addressError : undefined}
        >
          <AddressAutocomplete
            id='location-address'
            value={panel.formState.address}
            onChange={(val) => {
              markTouched('address');
              panel.setFormState((prev) => ({
                ...prev,
                address: val,
              }));
            }}
            onSelect={handleAddressSelect}
            placeholder='Start typing an address...'
            countryCodes={countryCodes}
            inputClassName={showAddressError ? errorInputClassName : ''}
            hasError={showAddressError}
            onBlur={() => markTouched('address')}
          />
        </AdminField>
        <AdminField span={2}>
          <CascadingAreaSelect
            tree={tree}
            value={panel.formState.area_id}
            onChange={handleAreaChange}
            disableCountry
            required
            hasError={showAreaError}
            errorMessage={showAreaError ? areaError : undefined}
          />
        </AdminField>
        <AdminField label='Latitude' htmlFor='location-lat'>
          <Input
            id='location-lat'
            type='number'
            step='0.000001'
            value={panel.formState.lat}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                lat: e.target.value,
              }))
            }
          />
        </AdminField>
        <AdminField label='Longitude' htmlFor='location-lng'>
          <Input
            id='location-lng'
            type='number'
            step='0.000001'
            value={panel.formState.lng}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                lng: e.target.value,
              }))
            }
          />
        </AdminField>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='locations'>
      <div className='space-y-4'>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel={isAdmin ? 'Locations' : 'Your locations'}
        rows={filteredItems}
        getLabel={(item) => getAreaName(item.area_id)}
        middleColumnCount={2}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No locations match your search.'
            : 'No locations yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New location'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New location'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField>
              <Input
                id='location-search'
                placeholder='Search locations...'
                aria-label='Search locations'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Area</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority={addressColumnPriority}>
              Address
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>{getAreaName(item.area_id)}</span>
              <AdminDataTableCellMeta until={addressColumnPriority}>
                {item.address || '—'}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority={addressColumnPriority}>
              {renderAddressCell(item)}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          deleteRowActions(() => {
            const areaName = getAreaName(item.area_id);
            panel.handleDelete(
              areaName === '—' ? item : { ...item, name: areaName }
            );
          })
        }
      />
        {panel.confirmDialog}
      </div>
    </WorkspaceScopeGate>
  );
}
