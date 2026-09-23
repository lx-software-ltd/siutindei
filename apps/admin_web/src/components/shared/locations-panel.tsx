'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { useEditDeepLink } from '../../hooks/use-edit-deep-link';
import { useGeographicAreas } from '../../hooks/use-geographic-areas';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationsByMode } from '../../hooks/use-organizations-by-mode';
import { useResourcePanel } from '../../hooks/use-resource-panel';
import type { GeographicAreaNode } from '../../lib/api-client';
import { parseOptionalNumber } from '../../lib/number-parsers';
import type { ApiMode } from '../../lib/resource-api';
import { normalizeKey } from '../../lib/string-utils';
import type { Location } from '../../types/admin';
import {
  AddressAutocomplete,
  type AddressSelection,
} from '../ui/address-autocomplete';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { CascadingAreaSelect } from '../ui/cascading-area-select';
import { DataTable } from '../ui/data-table';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { SearchInput } from '../ui/search-input';
import { Select } from '../ui/select';
import { StatusBanner } from '../status-banner';


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
      alt=""
      aria-hidden="true"
      loading="lazy"
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
  const panel = useResourcePanel<Location, LocationFormState>(
    'locations',
    mode,
    emptyForm,
    itemToForm
  );
  useEditDeepLink(panel.items, panel.editingId, panel.startEdit);

  // Geographic area tree for cascading dropdowns
  const { tree, countryCodes, matchNominatimResult } = useGeographicAreas();

  const { items: organizations } = useOrganizationsByMode(mode, { limit: 200 });

  const areaNameById = useMemo(() => {
    const map = new Map<string, string>();
    function walkTree(nodes: GeographicAreaNode[]) {
      for (const node of nodes) {
        map.set(node.id, node.name);
        if (node.children) {
          walkTree(node.children);
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

  // Search state
  const [searchQuery, setSearchQuery] = useState('');

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    ['org_id', 'area_id', 'address'],
    formKey
  );
  const requiredIndicator = validation.requiredIndicator;
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  // For managers with a single org, auto-select and disable the dropdown
  const isSingleOrgManager = !isAdmin && organizations.length === 1;

  const { setFormState } = panel;

  useEffect(() => {
    if (isAdmin || organizations.length !== 1) {
      return;
    }
    const orgId = organizations[0].id;
    setFormState((prev) =>
      prev.org_id === orgId ? prev : { ...prev, org_id: orgId }
    );
  }, [isAdmin, organizations, setFormState]);

  const handleAddressSelect = (selection: AddressSelection) => {
    // Try to reverse-match the Nominatim result to the area tree
    const match = matchNominatimResult(selection.raw);
    panel.setFormState((prev) => ({
      ...prev,
      address: selection.displayName,
      lat: `${selection.lat}`,
      lng: `${selection.lng}`,
      // Auto-fill area_id if we found a match in the tree
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

  const orgError = panel.formState.org_id
    ? ''
    : 'Select an organization.';
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

  const columns = useMemo(
    () => [
      {
        key: 'area',
        header: 'Area',
        primary: true,
        render: (item: Location) => (
          <span className='font-medium'>{getAreaName(item.area_id)}</span>
        ),
      },
      ...(isAdmin
        ? [
            {
              key: 'organization',
              header: 'Organization',
              secondary: true,
              render: (item: Location) => (
                <span className='text-slate-600'>
                  {organizations.find((org) => org.id === item.org_id)?.name ||
                    item.org_id}
                </span>
              ),
            },
          ]
        : []),
      {
        key: 'address',
        header: 'Address',
        render: (item: Location) => renderAddressCell(item),
      },
    ],
    [getAreaName, isAdmin, organizations]
  );

  // Filter items based on search query
  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const orgName =
      organizations
        .find((org) => org.id === item.org_id)
        ?.name?.toLowerCase() || '';
    const areaName = getAreaName(item.area_id).toLowerCase();
    return (
      areaName.includes(query) ||
      item.address?.toLowerCase().includes(query) ||
      orgName.includes(query)
    );
  });

  const showOrgError = shouldShowError('org_id', orgError);
  const showAreaError = shouldShowError('area_id', areaError);
  const showAddressError = shouldShowError('address', addressError);

  return (
    <div className='space-y-6'>
      <Card title='Locations' description='Manage location entries.'>
        {panel.error && (
          <div className='mb-4'>
            <StatusBanner variant='error' title='Error'>
              {panel.error}
            </StatusBanner>
          </div>
        )}
        <div className='grid gap-4 md:grid-cols-2'>
          <div className='space-y-1'>
            <Label htmlFor='location-org'>
              Organization{' '}
              <span className='ml-1'>{requiredIndicator}</span>
            </Label>
            <Select
              id='location-org'
              value={panel.formState.org_id}
              onChange={(e) => {
                markTouched('org_id');
                panel.setFormState((prev) => ({
                  ...prev,
                  org_id: e.target.value,
                }));
              }}
              disabled={isSingleOrgManager}
              className={showOrgError ? errorInputClassName : ''}
              aria-invalid={showOrgError || undefined}
            >
              <option value=''>Select organization</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </Select>
            {showOrgError ? (
              <p className='text-xs text-red-600'>{orgError}</p>
            ) : null}
          </div>
          <div className='md:col-span-2 space-y-1'>
            <Label htmlFor='location-address'>Address</Label>
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
            {showAddressError ? (
              <p className='text-xs text-red-600'>{addressError}</p>
            ) : null}
          </div>
          <div className='md:col-span-2'>
            <CascadingAreaSelect
              tree={tree}
              value={panel.formState.area_id}
              onChange={handleAreaChange}
              disableCountry
              required
              hasError={showAreaError}
              errorMessage={showAreaError ? areaError : undefined}
            />
          </div>
          <div>
            <Label htmlFor='location-lat'>Latitude</Label>
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
          </div>
          <div>
            <Label htmlFor='location-lng'>Longitude</Label>
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
          </div>
        </div>
        <div className='mt-4 flex flex-wrap gap-3'>
          <Button
            type='button'
            onClick={handleSubmit}
            disabled={panel.isSaving}
          >
            {panel.editingId ? 'Update Location' : 'Add Location'}
          </Button>
          {panel.editingId && (
            <Button
              type='button'
              variant='secondary'
              onClick={panel.resetForm}
              disabled={panel.isSaving}
            >
              Cancel
            </Button>
          )}
        </div>
      </Card>

      <Card
        title='Existing Locations'
        description='Select a location to edit or delete.'
      >
        {panel.isLoading ? (
          <p className='text-sm text-slate-600'>Loading locations...</p>
        ) : panel.items.length === 0 ? (
          <p className='text-sm text-slate-600'>No locations yet.</p>
        ) : (
          <div className='space-y-4'>
            <div className='max-w-full sm:max-w-sm'>
              <SearchInput
                placeholder='Search locations...'
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <DataTable
              columns={columns}
              data={filteredItems}
              keyExtractor={(item) => item.id}
              onEdit={(item) => panel.startEdit(item)}
              onDelete={(item) =>
                panel.handleDelete({ ...item, name: getAreaName(item.area_id) })
              }
              nextCursor={panel.nextCursor}
              onLoadMore={panel.loadMore}
              isLoading={panel.isLoading}
              emptyMessage={
                searchQuery.trim()
                  ? 'No locations match your search.'
                  : 'No locations yet.'
              }
            />
          </div>
        )}
      </Card>
      {panel.confirmDialog}
    </div>
  );
}
