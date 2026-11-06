'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { formatAdminPageName } from '../../lib/admin-page-name';
import type { GeographicAreaNode } from '../../lib/api-client';
import { areaAncestry, pinOutsideDistrict } from '../../lib/location-districts';
import {
  buildAppleMapsUrl,
  buildGoogleMapsUrl,
  coordinatesChanged,
  locationCoordinates,
  nextOpenedCoordinates,
} from '../../lib/location-maps';
import { parseOptionalNumber } from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/api-client-admin';
import {
  DEFAULT_LOCATION_STATUS,
  isLocationClosed,
  isLocationStatus,
  LOCATION_STATUSES,
  type LocationStatus,
} from '../../lib/location-status';
import { normalizeKey } from '../../lib/string-utils';
import type { Location } from '../../types/admin';
import { AppleMapsIcon, GoogleMapsIcon } from '../icons/action-icons';
import { ClosedLocationMark } from './closed-location-mark';
import { LocationPinMap } from './location-pin-map';
import { AdminCreateButton } from '../ui/admin-create-button';
import { adminTableText, AdminTableName } from '../ui/admin-table-value';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import {
  AddressAutocomplete,
  type AddressSelection,
} from '../ui/address-autocomplete';
import { CascadingAreaSelect } from '../ui/cascading-area-select';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { StatusBanner } from '../status-banner';
import { locationFormFromSnapshot } from '../admin/catalog-version-snapshot';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import {
  HistoricalRowMark,
  useCatalogVersion,
  VersionField,
  VersionFields,
  VersionSwitcher,
} from '../admin/version-history';
import { Button } from '../ui/button';
import { WorkspaceScopeGate } from '../admin/workspace-empty';

const PAGE_NAME = formatAdminPageName('Locations');

const MAP_ICON_CLASS = 'block h-4 w-4 shrink-0';

const CLOSED_DETAILS_HINT =
  'Address, area, latitude, and longitude stay unchanged while this location is closed.';

function MapServiceLink({
  href,
  label,
  children,
}: {
  href: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <a
      href={href}
      target='_blank'
      rel='noreferrer'
      title={label}
      aria-label={label}
      className='inline-flex h-4 w-4 shrink-0 items-center justify-center text-ink-500 hover:text-ink-900'
    >
      {children}
    </a>
  );
}

interface LocationFormState {
  org_id: string;
  area_id: string;
  name: string;
  status: LocationStatus;
  address: string;
  lat: string;
  lng: string;
}

const emptyForm: LocationFormState = {
  org_id: '',
  area_id: '',
  name: '',
  status: DEFAULT_LOCATION_STATUS,
  address: '',
  lat: '',
  lng: '',
};

function itemToForm(item: Location): LocationFormState {
  return {
    org_id: item.org_id ?? '',
    area_id: item.area_id ?? '',
    name: item.name ?? '',
    status: isLocationStatus(item.status) ? item.status : DEFAULT_LOCATION_STATUS,
    address: item.address ?? '',
    lat: item.lat !== undefined && item.lat !== null ? `${item.lat}` : '',
    lng: item.lng !== undefined && item.lng !== null ? `${item.lng}` : '',
  };
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

  const [statusError, setStatusError] = useState('');
  const [openedPin, setOpenedPin] = useState<{
    key: string;
    lat: string;
    lng: string;
  } | null>(null);

  const handleAreaChange = (areaId: string, _chain: GeographicAreaNode[]) => {
    markTouched('area_id');
    setStatusError('');
    panel.setFormState((prev) => ({ ...prev, area_id: areaId }));
  };

  const handleStatusChange = (status: LocationStatus) => {
    if (isLocationClosed(status) && !panel.formState.area_id) {
      setStatusError('Choose an area before closing this location.');
    } else {
      setStatusError('');
    }
    panel.setFormState((prev) => {
      if (!isLocationClosed(status) || !panel.editingId) {
        return { ...prev, status };
      }
      const saved = panel.items.find((item) => item.id === panel.editingId);
      if (!saved) {
        return { ...prev, status };
      }
      const restored = itemToForm(saved);
      return {
        ...prev,
        status,
        area_id: restored.area_id,
        address: restored.address,
        lat: restored.lat,
        lng: restored.lng,
      };
    });
  };

  const validate = () => {
    if (isLocationClosed(panel.formState.status) && !panel.formState.area_id) {
      return 'Choose an area before closing this location.';
    }
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
    name: form.name.trim() || null,
    status: form.status,
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
      <div className='flex items-center gap-2'>
        <span>{adminTableText(item.address)}</span>
        {hasMapLinks && (
          <span className='inline-flex h-4 items-center gap-2'>
            {googleMapsUrl && (
              <MapServiceLink href={googleMapsUrl} label='Open in Google Maps'>
                <GoogleMapsIcon className={MAP_ICON_CLASS} />
              </MapServiceLink>
            )}
            {appleMapsUrl && (
              <MapServiceLink href={appleMapsUrl} label='Open in Apple Maps'>
                <AppleMapsIcon className={MAP_ICON_CLASS} />
              </MapServiceLink>
            )}
          </span>
        )}
      </div>
    );
  }

  const showAreaError = shouldShowError('area_id', areaError);
  const showAddressError = shouldShowError('address', addressError);
  const addressColumnPriority = 'secondary' as const;
  const versionView = useCatalogVersion({
    mode,
    entityType: 'location',
    entityId: panel.editingId,
    version: panel.items.find((item) => item.id === panel.editingId)?.version,
  });
  const locked = versionView.locked;
  const editorForm = versionView.snapshot
    ? locationFormFromSnapshot(versionView.snapshot, panel.formState)
    : panel.formState;
  const detailsLocked =
    locked ||
    (isLocationClosed(editorForm.status) && Boolean(editorForm.area_id));
  const outsideDistrict = useMemo(() => {
    const placed = locationCoordinates({
      lat: editorForm.lat,
      lng: editorForm.lng,
    });
    if (!placed || !editorForm.area_id) {
      return false;
    }
    return pinOutsideDistrict(
      placed.lat,
      placed.lng,
      areaAncestry(tree, editorForm.area_id)
    );
  }, [editorForm.area_id, editorForm.lat, editorForm.lng, tree]);
  const openKey = panel.editingId ?? (panel.isDraftOpen ? 'draft' : null);
  const openedSource = panel.editingId
    ? panel.items.find((item) => item.id === panel.editingId)
    : undefined;
  const savedPin = openedSource
    ? { lat: itemToForm(openedSource).lat, lng: itemToForm(openedSource).lng }
    : null;
  const resolvedPin = nextOpenedCoordinates(openedPin, openKey, savedPin, {
    lat: panel.formState.lat,
    lng: panel.formState.lng,
  });
  if (resolvedPin !== openedPin) {
    setOpenedPin(resolvedPin);
  }
  const coordinatesDirty =
    resolvedPin !== null &&
    resolvedPin.key === openKey &&
    !detailsLocked &&
    coordinatesChanged(editorForm, resolvedPin);

  const detail = (
    <AdminEditorPanel
      accessory={
        panel.editingId ? <VersionSwitcher view={versionView} /> : undefined
      }
      status={
        panel.error ? (
          <StatusBanner kind='error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        versionView.isHistorical ? (
          <Button type='button' variant='secondary' onClick={versionView.backToLatest}>
            Back to latest
          </Button>
        ) : (
          <AdminEditorActions
            mode={panel.editorMode}
            onSubmit={handleSubmit}
            isSaving={panel.isSaving}
          />
        )
      }
    >
      <VersionFields view={versionView}>
      <div className='space-y-4'>
      <AdminFieldGrid columns={2}>
        <VersionField
          label='Name'
          htmlFor='location-name'
          versionKey='name'
        >
          <Input
            id='location-name'
            value={editorForm.name}
            maxLength={200}
            disabled={locked}
            onChange={(event) =>
              panel.setFormState((prev) => ({
                ...prev,
                name: event.target.value,
              }))
            }
          />
        </VersionField>
        <VersionField
          label='Status'
          htmlFor='location-status'
          versionKey='status'
          hint={
            isLocationClosed(editorForm.status) ? CLOSED_DETAILS_HINT : undefined
          }
          error={statusError || undefined}
        >
          <Select
            id='location-status'
            value={editorForm.status}
            disabled={locked}
            onChange={(event) => {
              const status = event.target.value;
              if (!isLocationStatus(status)) {
                return;
              }
              handleStatusChange(status);
            }}
          >
            {LOCATION_STATUSES.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </VersionField>
        <VersionField
          label='Address'
          htmlFor='location-address'
          span={2}
          versionKey='address'
          error={showAddressError ? addressError : undefined}
        >
          <AddressAutocomplete
            id='location-address'
            value={editorForm.address}
            disabled={detailsLocked}
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
        </VersionField>
        <VersionField span={2} versionKey='area_id'>
          <CascadingAreaSelect
            tree={tree}
            value={editorForm.area_id}
            onChange={handleAreaChange}
            disableCountry
            disabled={detailsLocked}
            required
            hasError={showAreaError}
            errorMessage={showAreaError ? areaError : undefined}
          />
        </VersionField>
        <VersionField label='Latitude' htmlFor='location-lat' versionKey='lat'>
          <Input
            id='location-lat'
            type='number'
            step='0.000001'
            value={editorForm.lat}
            disabled={detailsLocked}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                lat: e.target.value,
              }))
            }
          />
        </VersionField>
        <VersionField label='Longitude' htmlFor='location-lng' versionKey='lng'>
          <Input
            id='location-lng'
            type='number'
            step='0.000001'
            value={editorForm.lng}
            disabled={detailsLocked}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                lng: e.target.value,
              }))
            }
          />
        </VersionField>
      </AdminFieldGrid>
      <LocationPinMap
        lat={editorForm.lat}
        lng={editorForm.lng}
        readOnly={detailsLocked}
        onChange={(nextLat, nextLng) => {
          panel.setFormState((prev) => ({
            ...prev,
            lat: nextLat,
            lng: nextLng,
          }));
        }}
      />
      {outsideDistrict || coordinatesDirty ? (
        <div className='flex items-baseline gap-3'>
          {outsideDistrict ? (
            <p className='text-sm text-ink-700'>Pin is outside this district.</p>
          ) : null}
          {coordinatesDirty ? (
            <button
              type='button'
              className='admin-focus shrink-0 text-sm text-ink-700 underline underline-offset-2 hover:text-ink-900'
              aria-label='Reset coordinates'
              onClick={() => {
                panel.setFormState((prev) => ({
                  ...prev,
                  lat: resolvedPin?.lat ?? prev.lat,
                  lng: resolvedPin?.lng ?? prev.lng,
                }));
              }}
            >
              Reset
            </button>
          ) : null}
        </div>
      ) : null}
      </div>
      </VersionFields>
    </AdminEditorPanel>
  );

  return (
    <WorkspaceScopeGate orgId={scopedOrgId} isAdmin={isAdmin} noun='locations'>
      <div className='space-y-4'>
        <h2 className='sr-only'>{PAGE_NAME}</h2>
        <OrganizationWorkspaceTitle mode={mode} orgId={scopedOrgId} />
        <ResourceTableShell
        ariaLabel={PAGE_NAME}
        rows={panel.items}
        getLabel={(item) => getAreaName(item.area_id)}
        middleColumnCount={2}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel='No locations yet.'
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New location'
        onToggleDraft={panel.collapse}
        detail={detail}
        actions={
          panel.canCreate ? (
            <AdminCreateButton
              label='New location'
              active={panel.isDraftOpen}
              onClick={panel.openDraft}
            />
          ) : null
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
              <span className='inline-flex items-center'>
                <AdminTableName>{getAreaName(item.area_id)}</AdminTableName>
                <ClosedLocationMark
                  status={
                    item.id === panel.editingId && !versionView.isHistorical
                      ? editorForm.status
                      : item.status
                  }
                />
                <HistoricalRowMark
                  active={versionView.isHistorical && item.id === panel.editingId}
                  version={versionView.selectedVersion}
                />
              </span>
              <AdminDataTableCellMeta until={addressColumnPriority} label='Address'>
                {adminTableText(item.address)}
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
            // The confirm dialog reads `name`. That slot stays the area.
            panel.handleDelete({
              ...item,
              name: areaName === '—' ? undefined : areaName,
            });
          })
        }
      />
        {panel.confirmDialog}
      </div>
    </WorkspaceScopeGate>
  );
}
