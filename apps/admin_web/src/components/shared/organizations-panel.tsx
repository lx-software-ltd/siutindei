'use client';

import {
  useEffect,
  useMemo,
  useState,
  type ReactElement,
} from 'react';

import {
  getCountries,
  getCountryCallingCode,
} from 'libphonenumber-js';

import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useFormValidation } from '../../hooks/use-form-validation';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { ApiError } from '../../lib/api-client';
import { listCognitoUsers } from '../../lib/api-client-cognito';
import type { ApiMode } from '../../lib/resource-api';
import { normalizeKey } from '../../lib/string-utils';
import {
  buildTranslationsPayload,
  type LanguageCode,
} from '../../lib/translations';
import type { CognitoUser, Organization } from '../../types/admin';
import { useAuth } from '../auth-provider';
import { AdminCreateButton } from '../ui/admin-create-button';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '../ui/admin-data-table';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFieldGrid } from '../ui/admin-field-grid';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Select } from '../ui/select';
import { StatusBadge } from '../ui/status-badge';
import { StatusBanner } from '../status-banner';
import {
  ContactIcon,
  EmailIcon,
  PhoneIcon,
  ServiceIcon,
  SOCIAL_FIELDS,
  emptyForm,
  getManagerDisplayName,
  hasValue,
  isValidEmail,
  isValidPhoneNumber,
  isValidSocialValue,
  itemToForm,
  normalizePhoneNumber,
  normalizeSocialValue,
  type OrganizationFormState,
  type SocialFieldKey,
} from './organizations/organization-form-utils';

interface OrganizationsPanelProps {
  mode: ApiMode;
}

export function OrganizationsPanel({ mode }: OrganizationsPanelProps) {
  const isAdmin = mode === 'admin';
  const isManager = mode === 'manager';
  const { user } = useAuth();
  const panel = useResourceEditor<Organization, OrganizationFormState>({
    resource: 'organizations',
    mode,
    emptyForm,
    itemToForm,
    paramName: 'organization',
    legacyParam: 'edit',
    autoExpandFirst: isManager,
    noun: 'organization',
  });

  // Admin-only: Load Cognito users for manager selection
  const [cognitoUsers, setCognitoUsers] = useState<CognitoUser[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(isAdmin);

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [reviewFilter, setReviewFilter] = useState('all');
  useExhaustPages(Boolean(searchQuery.trim()), {
    hasMore: panel.hasMore,
    isLoading: panel.isLoading,
    isLoadingMore: panel.isLoadingMore,
    error: panel.listError,
    loadMore: panel.loadMore,
  });

  const formKey = panel.editingId ?? 'new';
  const validation = useFormValidation(
    [
      'name',
      'manager_id',
      'email',
      'phone_country_code',
      'phone_number',
      ...SOCIAL_FIELDS.map((field) => field.key),
    ],
    formKey
  );
  const requiredIndicator = validation.requiredIndicator;
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';
  const { markTouched } = validation;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  // Extract setError for stable reference in useEffect
  const { setError } = panel;

  useEffect(() => {
    if (!isAdmin) return;

    const loadCognitoUsers = async () => {
      setIsLoadingUsers(true);
      try {
        const allUsers: CognitoUser[] = [];
        let paginationToken: string | undefined;

        do {
          const response = await listCognitoUsers(paginationToken, 60);
          allUsers.push(...response.items);
          paginationToken = response.pagination_token ?? undefined;
        } while (paginationToken);

        setCognitoUsers(allUsers);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load users for manager selection.';
        setError(message);
      } finally {
        setIsLoadingUsers(false);
      }
    };

    loadCognitoUsers();
  }, [isAdmin, setError]);

  const countryOptions = useMemo(() => {
    const display =
      typeof Intl !== 'undefined' &&
      typeof Intl.DisplayNames === 'function'
        ? new Intl.DisplayNames(['en'], { type: 'region' })
        : null;
    return getCountries()
      .map((country) => {
        const callingCode = getCountryCallingCode(country);
        const name = display?.of(country) ?? country;
        return {
          code: country,
          label: `${name} (+${callingCode})`,
        };
      })
      .sort((a, b) => a.label.localeCompare(b.label));
  }, []);

  const validate = () => {
    if (!panel.formState.name.trim()) {
      return 'Name is required.';
    }
    const normalizedName = normalizeKey(panel.formState.name);
    const hasDuplicate = panel.items.some((item) => {
      if (!item.name) {
        return false;
      }
      if (panel.editingId && item.id === panel.editingId) {
        return false;
      }
      return normalizeKey(item.name) === normalizedName;
    });
    if (hasDuplicate) {
      return 'Organization name must be unique (case-insensitive).';
    }
    if (isAdmin && !panel.formState.manager_id) {
      return 'Manager is required.';
    }
    const email = panel.formState.email.trim();
    if (email && !isValidEmail(email)) {
      return 'Email is invalid.';
    }
    const phoneNumber = panel.formState.phone_number.trim();
    const phoneCountryCode = panel.formState.phone_country_code.trim();
    if (phoneNumber) {
      const normalizedNumber = normalizePhoneNumber(phoneNumber);
      if (!normalizedNumber) {
        return 'Phone number must contain digits.';
      }
      if (!phoneCountryCode) {
        return 'Phone country code is required.';
      }
      if (!isValidPhoneNumber(phoneCountryCode, normalizedNumber)) {
        return 'Phone number is invalid for selected country.';
      }
    }
    for (const field of SOCIAL_FIELDS) {
      const value = panel.formState[field.key].trim();
      if (!value) {
        continue;
      }
      if (!isValidSocialValue(value)) {
        return `${field.label} must be a valid handle or URL.`;
      }
    }
    return null;
  };

  const nameError = useMemo(() => {
    const trimmedName = panel.formState.name.trim();
    if (!trimmedName) {
      return 'Enter an organization name.';
    }
    const normalizedName = normalizeKey(trimmedName);
    const hasDuplicate = panel.items.some((item) => {
      if (!item.name) {
        return false;
      }
      if (panel.editingId && item.id === panel.editingId) {
        return false;
      }
      return normalizeKey(item.name) === normalizedName;
    });
    if (hasDuplicate) {
      return 'Name already exists.';
    }
    return '';
  }, [panel.editingId, panel.formState.name, panel.items]);

  const managerError =
    isAdmin && !panel.formState.manager_id ? 'Select a manager.' : '';

  const emailError = useMemo(() => {
    const trimmed = panel.formState.email.trim();
    if (!trimmed) {
      return '';
    }
    return isValidEmail(trimmed) ? '' : 'Enter a valid email address.';
  }, [panel.formState.email]);

  const { phoneCountryError, phoneNumberError } = useMemo(() => {
    const phoneNumber = panel.formState.phone_number.trim();
    const phoneCountryCode = panel.formState.phone_country_code.trim();
    if (!phoneNumber) {
      return { phoneCountryError: '', phoneNumberError: '' };
    }
    const normalizedNumber = normalizePhoneNumber(phoneNumber);
    if (!normalizedNumber) {
      return {
        phoneCountryError: '',
        phoneNumberError: 'Enter digits only.',
      };
    }
    if (!phoneCountryCode) {
      return {
        phoneCountryError: 'Select a country code.',
        phoneNumberError: '',
      };
    }
    if (!isValidPhoneNumber(phoneCountryCode, normalizedNumber)) {
      return {
        phoneCountryError: '',
        phoneNumberError: 'Enter a valid phone number.',
      };
    }
    return { phoneCountryError: '', phoneNumberError: '' };
  }, [panel.formState.phone_country_code, panel.formState.phone_number]);

  const socialErrors = useMemo(() => {
    const errors: Record<SocialFieldKey, string> = {
      whatsapp: '',
      facebook: '',
      instagram: '',
      tiktok: '',
      twitter: '',
      xiaohongshu: '',
      wechat: '',
    };
    for (const field of SOCIAL_FIELDS) {
      const value = panel.formState[field.key].trim();
      if (!value) {
        continue;
      }
      if (!isValidSocialValue(value)) {
        errors[field.key] = 'Enter a valid handle or URL.';
      }
    }
    return errors;
  }, [panel.formState]);

  const handleNameChange = (language: LanguageCode, value: string) => {
    markTouched('name');
    panel.setFormState((prev) =>
      language === 'en'
        ? { ...prev, name: value }
        : {
            ...prev,
            name_translations: {
              ...prev.name_translations,
              [language]: value,
            },
          }
    );
  };

  const handleDescriptionChange = (language: LanguageCode, value: string) => {
    panel.setFormState((prev) =>
      language === 'en'
        ? { ...prev, description: value }
        : {
            ...prev,
            description_translations: {
              ...prev.description_translations,
              [language]: value,
            },
          }
    );
  };

  const formToPayload = (form: OrganizationFormState) => {
    const existingOrg = panel.items.find((item) => item.id === panel.editingId);
    const phoneNumber = normalizePhoneNumber(form.phone_number);
    const email = form.email.trim();
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      name_translations: buildTranslationsPayload(form.name_translations),
      description_translations: buildTranslationsPayload(
        form.description_translations
      ),
      media_urls: existingOrg?.media_urls ?? [],
      phone_country_code: phoneNumber
        ? form.phone_country_code.trim().toUpperCase()
        : null,
      phone_number: phoneNumber || null,
      email: email || null,
      whatsapp: normalizeSocialValue(form.whatsapp),
      facebook: normalizeSocialValue(form.facebook),
      instagram: normalizeSocialValue(form.instagram),
      tiktok: normalizeSocialValue(form.tiktok),
      twitter: normalizeSocialValue(form.twitter),
      xiaohongshu: normalizeSocialValue(form.xiaohongshu),
      wechat: normalizeSocialValue(form.wechat),
    };
    if (isAdmin) {
      payload.manager_id = form.manager_id;
      payload.status = form.status;
      payload.status_source = 'owner';
    }
    return payload;
  };

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

  // Filter items based on search query
  const filteredItems = panel.items.filter((item) => {
    if (
      reviewFilter !== 'all' &&
      (item.review_status ?? 'pending_review') !== reviewFilter
    ) {
      return false;
    }
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const nameTranslations = Object.values(item.name_translations ?? {})
      .join(' ')
      .toLowerCase();
    const descriptionTranslations = Object.values(
      item.description_translations ?? {}
    )
      .join(' ')
      .toLowerCase();
    const managerDisplay = getManagerDisplayName(item.manager_id, cognitoUsers).toLowerCase();
    return (
      item.name?.toLowerCase().includes(query) ||
      item.description?.toLowerCase().includes(query) ||
      nameTranslations.includes(query) ||
      descriptionTranslations.includes(query) ||
      managerDisplay.includes(query)
    );
  });

  const showNameError = shouldShowError('name', nameError);
  const showManagerError = shouldShowError('manager_id', managerError);
  const showEmailError = shouldShowError('email', emailError);
  const showPhoneCountryError = shouldShowError(
    'phone_country_code',
    phoneCountryError
  );
  const showPhoneNumberError = shouldShowError(
    'phone_number',
    phoneNumberError
  );

  const showSocialError = (key: SocialFieldKey) =>
    shouldShowError(key, socialErrors[key]);

  const renderContactIcons = (item: Organization) => {
    const icons: ReactElement[] = [];
    if (hasValue(item.phone_country_code) && hasValue(item.phone_number)) {
      icons.push(
        <ContactIcon key='phone' label='Phone'>
          <PhoneIcon className='h-4 w-4' />
        </ContactIcon>
      );
    }
    if (hasValue(item.email)) {
      icons.push(
        <ContactIcon key='email' label='Email'>
          <EmailIcon className='h-4 w-4' />
        </ContactIcon>
      );
    }
    for (const field of SOCIAL_FIELDS) {
      const value = item[field.key];
      if (!hasValue(value)) {
        continue;
      }
      icons.push(
        <ContactIcon key={field.key} label={field.label}>
          <ServiceIcon className='h-4 w-4' src={field.iconSrc} />
        </ContactIcon>
      );
    }
    if (icons.length === 0) {
      return <span className='text-slate-400'>—</span>;
    }
    return (
      <div className='flex flex-wrap items-center gap-2 text-slate-500'>
        {icons}
      </div>
    );
  };

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner variant='error' title='Error'>
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
            <div className='space-y-1'>
              <LanguageToggleInput
                id='org-name'
                label='Name'
                required
                values={{
                  en: panel.formState.name,
                  zh: panel.formState.name_translations.zh,
                  yue: panel.formState.name_translations.yue,
                }}
                onChange={handleNameChange}
                hasError={showNameError}
                inputClassName={showNameError ? errorInputClassName : ''}
              />
              {showNameError ? (
                <p className='text-xs text-red-600'>{nameError}</p>
              ) : null}
            </div>
            <div>
              <Label htmlFor='org-manager'>
                Manager
                {isAdmin ? (
                  <span className='ml-1'>{requiredIndicator}</span>
                ) : null}
              </Label>
              {isAdmin ? (
                <Select
                  id='org-manager'
                  value={panel.formState.manager_id}
                  onChange={(e) => {
                    markTouched('manager_id');
                    panel.setFormState((prev) => ({
                      ...prev,
                      manager_id: e.target.value,
                    }));
                  }}
                  disabled={isLoadingUsers}
                  className={showManagerError ? errorInputClassName : ''}
                  aria-invalid={showManagerError || undefined}
                >
                  <option value=''>
                    {isLoadingUsers ? 'Loading users...' : 'Select a manager'}
                  </option>
                  {cognitoUsers.map((cognitoUser) => (
                    <option key={cognitoUser.sub} value={cognitoUser.sub}>
                      {cognitoUser.email || cognitoUser.username || cognitoUser.sub}
                      {cognitoUser.name ? ` (${cognitoUser.name})` : ''}
                    </option>
                  ))}
                </Select>
              ) : (
                <Select
                  id='org-manager'
                  value={user?.email ?? ''}
                  disabled
                  className={showManagerError ? errorInputClassName : ''}
                >
                  <option value={user?.email ?? ''}>
                    {user?.email ?? 'Unknown'}
                  </option>
                </Select>
              )}
              {showManagerError ? (
                <p className='text-xs text-red-600'>{managerError}</p>
              ) : null}
            </div>
            <div className='md:col-span-2'>
              <LanguageToggleInput
                id='org-description'
                label='Description'
                multiline
                rows={3}
                values={{
                  en: panel.formState.description,
                  zh: panel.formState.description_translations.zh,
                  yue: panel.formState.description_translations.yue,
                }}
                onChange={handleDescriptionChange}
              />
            </div>
            <div className='md:col-span-2 space-y-1'>
              <Label htmlFor='org-email'>Email</Label>
              <Input
                id='org-email'
                type='email'
                value={panel.formState.email}
                onChange={(e) => {
                  markTouched('email');
                  panel.setFormState((prev) => ({
                    ...prev,
                    email: e.target.value,
                  }));
                }}
                placeholder='contact@example.com'
                className={showEmailError ? errorInputClassName : ''}
                aria-invalid={showEmailError || undefined}
              />
              {showEmailError ? (
                <p className='text-xs text-red-600'>{emailError}</p>
              ) : null}
            </div>
            <div className='space-y-1'>
              <Label htmlFor='org-phone-country'>Phone country</Label>
              <Select
                id='org-phone-country'
                value={panel.formState.phone_country_code}
                onChange={(e) => {
                  markTouched('phone_country_code');
                  panel.setFormState((prev) => ({
                    ...prev,
                    phone_country_code: e.target.value,
                  }));
                }}
                className={showPhoneCountryError ? errorInputClassName : ''}
                aria-invalid={showPhoneCountryError || undefined}
              >
                {countryOptions.map((option) => (
                  <option key={option.code} value={option.code}>
                    {option.label}
                  </option>
                ))}
              </Select>
              {showPhoneCountryError ? (
                <p className='text-xs text-red-600'>{phoneCountryError}</p>
              ) : null}
            </div>
            <div className='space-y-1'>
              <Label htmlFor='org-phone-number'>Phone number</Label>
              <Input
                id='org-phone-number'
                type='tel'
                inputMode='numeric'
                value={panel.formState.phone_number}
                onChange={(e) => {
                  markTouched('phone_number');
                  panel.setFormState((prev) => ({
                    ...prev,
                    phone_number: e.target.value,
                  }));
                }}
                placeholder='1234 5678'
                className={showPhoneNumberError ? errorInputClassName : ''}
                aria-invalid={showPhoneNumberError || undefined}
              />
              {showPhoneNumberError ? (
                <p className='text-xs text-red-600'>{phoneNumberError}</p>
              ) : null}
            </div>
            {isAdmin && (
              <div className='space-y-1'>
                <Label htmlFor='org-listing-status'>Listing status</Label>
                <Select
                  id='org-listing-status'
                  value={panel.formState.status}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      status: event.target.value,
                    }))
                  }
                >
                  <option value='operational'>Operational</option>
                  <option value='closed_temporarily'>Closed temporarily</option>
                  <option value='closed_permanently'>Closed permanently</option>
                  <option value='hidden'>Hidden</option>
                </Select>
                {panel.editingId && (
                  <p className='text-xs text-slate-500'>
                    Review state is changed from Imports → Review queue.
                    Current review:{' '}
                    {(
                      panel.items.find((item) => item.id === panel.editingId)
                        ?.review_status ?? 'pending_review'
                    ).replaceAll('_', ' ')}
                    .
                  </p>
                )}
              </div>
            )}
            <div className='md:col-span-2 border-t border-slate-100 pt-4'>
              <p className='text-sm font-medium text-slate-700'>Social</p>
              <p className='text-xs text-slate-500'>
                Use @handle or https:// URLs for each network.
              </p>
            </div>
            {SOCIAL_FIELDS.map((field) => {
              const showError = showSocialError(field.key);
              return (
                <div key={field.key} className='space-y-1'>
                  <Label htmlFor={`org-${field.key}`}>{field.label}</Label>
                  <Input
                    id={`org-${field.key}`}
                    value={panel.formState[field.key]}
                    onChange={(e) => {
                      markTouched(field.key);
                      panel.setFormState((prev) => ({
                        ...prev,
                        [field.key]: e.target.value,
                      }));
                    }}
                    placeholder='@handle or https://...'
                    className={showError ? errorInputClassName : ''}
                    aria-invalid={showError || undefined}
                  />
                  {showError ? (
                    <p className='text-xs text-red-600'>
                      {socialErrors[field.key]}
                    </p>
                  ) : null}
                </div>
              );
            })}
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <>
      <ResourceTableShell
        ariaLabel={isAdmin ? 'Organizations' : 'Your organizations'}
        rows={filteredItems}
        getLabel={(item) => item.name || 'Organization'}
        middleColumnCount={isAdmin ? 6 : 5}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No organizations match your search.'
            : 'No organizations yet.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New organization'
        onToggleDraft={panel.collapse}
        detail={detail}
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New organization'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField label='Search' htmlFor='org-search'>
              <Input
                id='org-search'
                placeholder='Search organizations...'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
            <AdminFilterField label='Review' htmlFor='org-review-filter'>
              <Select
                id='org-review-filter'
                value={reviewFilter}
                onChange={(event) => setReviewFilter(event.target.value)}
              >
                <option value='all'>All</option>
                <option value='pending_review'>Pending review</option>
                <option value='approved'>Approved</option>
                <option value='rejected'>Rejected</option>
              </Select>
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Name</AdminDataTableHeadCell>
            {isAdmin ? (
              <AdminDataTableHeadCell priority='secondary'>
                Manager
              </AdminDataTableHeadCell>
            ) : null}
            <AdminDataTableHeadCell priority='secondary'>
              Status
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Review
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Description
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Contact
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              {item.name}
              <AdminDataTableCellMeta until='tertiary'>
                {(item.review_status ?? 'pending_review').replaceAll('_', ' ')}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            {isAdmin ? (
              <AdminDataTableCell priority='secondary'>
                {getManagerDisplayName(item.manager_id, cognitoUsers)}
              </AdminDataTableCell>
            ) : null}
            <AdminDataTableCell priority='secondary'>
              <StatusBadge
                status={(item.status ?? 'operational').replaceAll('_', ' ')}
              />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <StatusBadge
                status={(item.review_status ?? 'pending_review').replaceAll(
                  '_',
                  ' '
                )}
              />
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              {item.description || '—'}
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              {renderContactIcons(item)}
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) => deleteRowActions(() => panel.handleDelete(item))}
      />
      {panel.confirmDialog}
    </>
  );
}
