'use client';

import { useEffect, useMemo, useState } from 'react';

import {
  getCountries,
  getCountryCallingCode,
} from 'libphonenumber-js';

import { useFormValidation } from '../../hooks/use-form-validation';
import { useOrganizationScope } from '../../hooks/use-organization-scope';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { listResource } from '../../lib/api-client-admin';
import type { ApiMode } from '../../lib/resource-api';
import { normalizeKey } from '../../lib/string-utils';
import {
  buildTranslationsPayload,
  type LanguageCode,
} from '../../lib/translations';
import type { Organization } from '../../types/admin';
import { OrganizationMergeDialog } from '../admin/data-quality/organization-merge-dialog';
import { OrganizationReadiness } from '../admin/organization-readiness';
import { OrganizationWorkspaceTitle } from '../admin/organization-workspace-title';
import { WorkspaceEmpty } from '../admin/workspace-empty';
import { useAuth } from '../auth-provider';
import { Button } from '../ui/button';
import { AdminEditorActions, AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminField, AdminFieldGrid, formErrorClassName } from '../ui/admin-field-grid';
import { Input } from '../ui/input';
import { LanguageToggleInput } from '../ui/language-toggle-input';
import { Card } from '../ui/card';
import { Select } from '../ui/select';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';
import { ManagerCombobox } from './organizations/manager-combobox';
import {
  SOCIAL_FIELDS,
  DESCRIPTION_SOURCE_OPTIONS,
  emptyForm,
  ORG_SOURCE_OPTIONS,
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
  onOrganizationRemoved?: () => void;
}

async function organizationNameTaken(
  name: string,
  editingId: string | null
): Promise<boolean> {
  const page = await listResource<Organization>(
    'organizations',
    undefined,
    50,
    undefined,
    { q: name.trim() }
  );
  const key = normalizeKey(name);
  return page.items.some(
    (item) =>
      item.id !== editingId &&
      Boolean(item.name) &&
      normalizeKey(item.name) === key
  );
}

export function OrganizationsPanel({
  mode,
  onOrganizationRemoved,
}: OrganizationsPanelProps) {
  const isAdmin = mode === 'admin';
  const isManager = mode === 'manager';
  const { user } = useAuth();
  const scope = useOrganizationScope();
  const panel = useResourceEditor<Organization, OrganizationFormState>({
    resource: 'organizations',
    mode,
    emptyForm,
    itemToForm,
    paramName: 'org',
    autoExpandFirst: isManager,
    enabled: isManager,
    noun: 'organization',
  });

  const [mergeAnchor, setMergeAnchor] = useState<{
    id: string;
    name: string;
  } | null>(null);
  const [remoteNameTaken, setRemoteNameTaken] = useState(false);
  const editorOpen = panel.isDraftOpen || Boolean(panel.editingId);

  const { orgParam, legacyOrgId, setOrg } = scope;
  useEffect(() => {
    if (orgParam || !legacyOrgId) {
      return;
    }
    setOrg(legacyOrgId);
  }, [legacyOrgId, orgParam, setOrg]);

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
  const errorInputClassName = formErrorClassName;
  const { markTouched } = validation;
  const { setError } = panel;
  const shouldShowError = (field: string, message: string) =>
    validation.shouldShowError(field, Boolean(message));

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    const trimmed = panel.formState.name.trim();
    if (!trimmed) {
      return;
    }
    let cancelled = false;
    const handle = window.setTimeout(() => {
      void organizationNameTaken(trimmed, panel.editingId)
        .then((taken) => {
          if (!cancelled) {
            setRemoteNameTaken(taken);
          }
        })
        .catch(() => {
          if (!cancelled) {
            setRemoteNameTaken(false);
          }
        });
    }, 300);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [isAdmin, panel.editingId, panel.formState.name]);

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

  const validate = async () => {
    if (!panel.formState.name.trim()) {
      return 'Name is required.';
    }
    const normalizedName = normalizeKey(panel.formState.name);
    const hasDuplicate = isAdmin
      ? await organizationNameTaken(panel.formState.name, panel.editingId)
      : panel.items.some((item) => {
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
    if (isAdmin && panel.editingId && !panel.formState.manager_id) {
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
    const hasDuplicate = isAdmin
      ? remoteNameTaken
      : panel.items.some((item) => {
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
  }, [isAdmin, panel.editingId, panel.formState.name, panel.items, remoteNameTaken]);

  const managerError =
    isAdmin && panel.editingId && !panel.formState.manager_id
      ? 'Select a manager.'
      : '';

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
      if (form.manager_id) {
        payload.manager_id = form.manager_id;
      }
      payload.status = form.status;
      payload.status_source = 'owner';
      payload.source = form.source || null;
      payload.source_id = form.source_id.trim() || null;
      payload.source_url = form.source_url.trim() || null;
      payload.source_note = form.source_note.trim() || null;
      payload.description_source = form.description_source || null;
    }
    return payload;
  };

  const handleSubmit = () => {
    validation.setHasSubmitted(true);
    validation.markAllTouched();
    return panel.handleSubmit(formToPayload, validate);
  };

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

  const detail = (
    <AdminEditorPanel
      status={
        panel.error ? (
          <StatusBanner variant='error' kind='error'>
            {panel.error}
          </StatusBanner>
        ) : null
      }
      actions={
        <AdminEditorActions
          mode={panel.editorMode}
          onSubmit={handleSubmit}
          isSaving={panel.isSaving}
        >
          {isAdmin && panel.editingId ? (
            <Button
              type='button'
              variant='secondary'
              onClick={() => {
                const current = panel.items.find(
                  (item) => item.id === panel.editingId
                );
                if (current) {
                  setMergeAnchor({ id: current.id, name: current.name });
                }
              }}
            >
              Merge into…
            </Button>
          ) : null}
          {panel.editingId ? (
            <Button
              type='button'
              variant='danger'
              onClick={() => {
                const current = panel.items.find(
                  (item) => item.id === panel.editingId
                );
                if (!current) {
                  return;
                }
                void panel.handleDelete(current).then((removed) => {
                  if (removed && isManager) {
                    onOrganizationRemoved?.();
                  }
                });
              }}
            >
              Delete
            </Button>
          ) : null}
        </AdminEditorActions>
      }
    >
      <AdminFieldGrid columns={2}>
            <AdminField error={showNameError ? nameError : undefined}>
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
            </AdminField>
            <AdminField
              label='Manager'
              htmlFor='org-manager'
              required={isAdmin && Boolean(panel.editingId)}
              error={showManagerError ? managerError : undefined}
            >
              {isAdmin ? (
                <ManagerCombobox
                  key={formKey}
                  id='org-manager'
                  value={panel.formState.manager_id}
                  onChange={(managerId) => {
                    markTouched('manager_id');
                    panel.setFormState((prev) => ({
                      ...prev,
                      manager_id: managerId,
                    }));
                  }}
                  onError={setError}
                  hasError={showManagerError}
                  allowEmpty={!panel.editingId}
                  inputClassName={
                    showManagerError ? errorInputClassName : ''
                  }
                />
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
            </AdminField>
            <AdminField span={2}>
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
            </AdminField>
            <AdminField
              label='Email'
              htmlFor='org-email'
              span={2}
              error={showEmailError ? emailError : undefined}
            >
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
            </AdminField>
            <AdminField
              label='Phone country'
              htmlFor='org-phone-country'
              error={showPhoneCountryError ? phoneCountryError : undefined}
            >
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
            </AdminField>
            <AdminField
              label='Phone number'
              htmlFor='org-phone-number'
              error={showPhoneNumberError ? phoneNumberError : undefined}
            >
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
            </AdminField>
            {isAdmin && (
              <>
              <AdminField label='Source' htmlFor='org-source'>
                <Select
                  id='org-source'
                  value={panel.formState.source}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      source: event.target.value,
                    }))
                  }
                >
                  <option value=''>None</option>
                  {ORG_SOURCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </AdminField>
              <AdminField label='Source ID' htmlFor='org-source-id'>
                <Input
                  id='org-source-id'
                  value={panel.formState.source_id}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      source_id: event.target.value,
                    }))
                  }
                />
              </AdminField>
              <AdminField label='Description origin' htmlFor='org-description-source'>
                <Select
                  id='org-description-source'
                  value={panel.formState.description_source}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      description_source: event.target.value,
                    }))
                  }
                >
                  <option value=''>None</option>
                  {DESCRIPTION_SOURCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </AdminField>
              <AdminField label='Source URL' htmlFor='org-source-url'>
                <Input
                  id='org-source-url'
                  type='url'
                  value={panel.formState.source_url}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      source_url: event.target.value,
                    }))
                  }
                  placeholder='https://'
                />
              </AdminField>
              <AdminField label='Source note' htmlFor='org-source-note' span={2}>
                <Textarea
                  id='org-source-note'
                  rows={2}
                  value={panel.formState.source_note}
                  onChange={(event) =>
                    panel.setFormState((prev) => ({
                      ...prev,
                      source_note: event.target.value,
                    }))
                  }
                />
              </AdminField>
              <AdminField
                label='Listing status'
                htmlFor='org-listing-status'
                hint={
                  panel.editingId
                    ? `Review state is changed from Readiness below. Current review: ${(
                        panel.items.find((item) => item.id === panel.editingId)
                          ?.review_status ?? 'pending_review'
                      ).replaceAll('_', ' ')}.`
                    : undefined
                }
              >
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
              </AdminField>
              </>
            )}
            {SOCIAL_FIELDS.map((field) => {
              const showError = showSocialError(field.key);
              return (
                <AdminField
                  key={field.key}
                  label={field.label}
                  htmlFor={`org-${field.key}`}
                  error={showError ? socialErrors[field.key] : undefined}
                >
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
                </AdminField>
              );
            })}
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  if (!editorOpen) {
    if (panel.isLoading || (isManager && panel.items.length > 0)) {
      return (
        <StatusBanner variant='info' kind='info'>
          Loading the organization…
        </StatusBanner>
      );
    }
    if (isManager) {
      return (
        <div className='rounded-lg border border-slate-200 bg-white p-6'>
          <p className='text-base font-semibold text-slate-900'>
            No organization is assigned
          </p>
          <p className='mt-1 text-sm text-slate-600'>
            This account does not have an organization to manage.
          </p>
        </div>
      );
    }
    return (
      <>
        {panel.listError ? (
          <StatusBanner variant='error' kind='error'>
            {panel.listError}
          </StatusBanner>
        ) : null}
        <WorkspaceEmpty noun='the organization' />
        {panel.confirmDialog}
      </>
    );
  }

  const current = panel.items.find((item) => item.id === panel.editingId);

  return (
    <div className='space-y-4'>
      {current ? (
        <OrganizationWorkspaceTitle
          mode={mode}
          orgId={current.id}
          organization={current}
        />
      ) : (
        <h2 className='text-lg font-semibold text-slate-900'>New organization</h2>
      )}
      <Card>{detail}</Card>
      {isAdmin && panel.editingId ? (
        <OrganizationReadiness orgId={panel.editingId} />
      ) : null}
      {isAdmin ? (
        <OrganizationMergeDialog
          anchor={mergeAnchor}
          onClose={() => setMergeAnchor(null)}
          onMerged={(survivorId) => {
            scope.setOrg(survivorId);
          }}
        />
      ) : null}
      {panel.confirmDialog}
    </div>
  );
}
