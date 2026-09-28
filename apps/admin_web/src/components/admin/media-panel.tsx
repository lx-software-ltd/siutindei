'use client';

import { useEffect, useReducer, useRef, useState } from 'react';
import type { ChangeEvent, DragEvent, SetStateAction } from 'react';

import {
  ApiError,
  updateResource,
} from '../../lib/api-client';
import {
  deleteOrganizationMedia,
} from '../../lib/api-client-media';
import { useConfirmDialog } from '../../hooks/use-confirm-dialog';
import { useOrganizationsByMode } from '../../hooks/use-organizations-by-mode';
import type { Organization } from '../../types/admin';
import { AdminEditorPanel } from '../ui/admin-editor-panel';
import { AdminFilterBar, AdminFilterField } from '../ui/admin-filter-bar';
import { Button } from '../ui/button';
import { Card } from '../ui/card';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { StatusBanner } from '../status-banner';
import { MediaGrid } from './media/media-grid';
import {
  initialMediaPanelState,
  isManagedMediaUrl,
  mediaPanelReducer,
  normalizeMediaUrls,
  reorderMediaUrls,
  resolveLogoMediaUrl,
  type MediaPanelProps,
  type MediaPanelState,
  uploadMediaFile,
} from './media/media-panel-utils';

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox='0 0 24 24'
      fill='none'
      stroke='currentColor'
      strokeWidth='2'
      strokeLinecap='round'
      strokeLinejoin='round'
    >
      <line x1='12' y1='5' x2='12' y2='19' />
      <line x1='5' y1='12' x2='19' y2='12' />
    </svg>
  );
}

export function MediaPanel({ mode = 'admin' }: MediaPanelProps) {
  const isAdmin = mode === 'admin';
  const {
    items: orgItems,
    isLoading: isLoadingOrgs,
    error: organizationsError,
  } = useOrganizationsByMode(mode, { fetchAll: true, limit: 50 });
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [mediaState, dispatchMedia] = useReducer(
    mediaPanelReducer,
    initialMediaPanelState
  );
  const {
    selectedOrgId,
    orgTouched,
    orgActionAttempted,
    isSaving,
    isProcessingMedia,
    error,
    successMessage,
    mediaUrls,
    logoMediaUrl,
    newMediaUrl,
    pendingMediaDeletes,
    uploadedMediaUrls,
    hasUnsavedChanges,
    dragIndex,
    dragOverIndex,
  } = mediaState;

  const setMediaField = <K extends keyof MediaPanelState>(
    field: K,
    value: SetStateAction<MediaPanelState[K]>
  ) => {
    if (typeof value === 'function') {
      dispatchMedia({
        type: 'set-field-updater',
        field,
        updater: value as (previous: unknown) => unknown,
      });
      return;
    }
    dispatchMedia({ type: 'set-field', field, value });
  };

  const setSelectedOrgId = (value: SetStateAction<string>) =>
    setMediaField('selectedOrgId', value);
  const setOrgTouched = (value: SetStateAction<boolean>) =>
    setMediaField('orgTouched', value);
  const setOrgActionAttempted = (value: SetStateAction<boolean>) =>
    setMediaField('orgActionAttempted', value);
  const setIsSaving = (value: SetStateAction<boolean>) =>
    setMediaField('isSaving', value);
  const setIsProcessingMedia = (value: SetStateAction<boolean>) =>
    setMediaField('isProcessingMedia', value);
  const setError = (value: SetStateAction<string>) =>
    setMediaField('error', value);
  const setSuccessMessage = (value: SetStateAction<string>) =>
    setMediaField('successMessage', value);
  const setMediaUrls = (value: SetStateAction<string[]>) =>
    setMediaField('mediaUrls', value);
  const setLogoMediaUrl = (value: SetStateAction<string | null>) =>
    setMediaField('logoMediaUrl', value);
  const setNewMediaUrl = (value: SetStateAction<string>) =>
    setMediaField('newMediaUrl', value);
  const setPendingMediaDeletes = (value: SetStateAction<string[]>) =>
    setMediaField('pendingMediaDeletes', value);
  const setUploadedMediaUrls = (value: SetStateAction<string[]>) =>
    setMediaField('uploadedMediaUrls', value);
  const setHasUnsavedChanges = (value: SetStateAction<boolean>) =>
    setMediaField('hasUnsavedChanges', value);
  const setDragIndex = (value: SetStateAction<number | null>) =>
    setMediaField('dragIndex', value);
  const setDragOverIndex = (value: SetStateAction<number | null>) =>
    setMediaField('dragOverIndex', value);
  const { confirm, confirmDialog } = useConfirmDialog();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const requiredIndicator = (
    <span className='text-red-500' aria-hidden='true'>
      *
    </span>
  );
  const errorInputClassName =
    'border-red-500 focus:border-red-500 focus:ring-red-500';

  const showOrgError =
    !selectedOrgId && (orgTouched || orgActionAttempted);
  const orgErrorMessage = showOrgError ? 'Select an organization.' : '';

  const isMediaBusy = isSaving || isProcessingMedia;

  // For managers with a single org, auto-select and disable the dropdown
  const isSingleOrgManager = !isAdmin && organizations.length === 1;

  const selectedOrganization = organizations.find(
    (org) => org.id === selectedOrgId
  );

  useEffect(() => {
    setOrganizations(orgItems);
    if (isAdmin || selectedOrgId) {
      return;
    }
    if (orgItems.length === 1) {
      const singleOrg = orgItems[0];
      const nextMediaUrls = singleOrg.media_urls ?? [];
      dispatchMedia({
        type: 'patch',
        payload: {
          selectedOrgId: singleOrg.id,
          orgTouched: false,
          orgActionAttempted: false,
          mediaUrls: nextMediaUrls,
          logoMediaUrl: resolveLogoMediaUrl(
            nextMediaUrls,
            singleOrg.logo_media_url
          ),
        },
      });
    }
  }, [isAdmin, orgItems, selectedOrgId]);

  useEffect(() => {
    if (organizationsError) {
      dispatchMedia({
        type: 'set-field',
        field: 'error',
        value: organizationsError,
      });
    }
  }, [organizationsError]);

  const handleSelectOrganization = async (orgId: string) => {
    if (hasUnsavedChanges) {
      const confirmed = await confirm(
        'Switch organizations?',
        'You have unsaved changes. Switch organizations and discard them?',
        { confirmLabel: 'Switch', variant: 'danger' }
      );
      if (!confirmed) {
        return;
      }
    }

    setSelectedOrgId(orgId);
    setOrgTouched(true);
    setOrgActionAttempted(false);
    setHasUnsavedChanges(false);
    setPendingMediaDeletes([]);
    setUploadedMediaUrls([]);
    setNewMediaUrl('');
    setError('');
    setSuccessMessage('');
    setDragIndex(null);
    setDragOverIndex(null);

    const org = organizations.find((o) => o.id === orgId);
    const nextMediaUrls = org?.media_urls ?? [];
    setMediaUrls(nextMediaUrls);
    setLogoMediaUrl(
      resolveLogoMediaUrl(nextMediaUrls, org?.logo_media_url)
    );
  };

  const handleAddMediaUrl = () => {
    const trimmed = newMediaUrl.trim();
    if (!trimmed) {
      return;
    }
    setMediaUrls((prev) => normalizeMediaUrls([...prev, trimmed]));
    setPendingMediaDeletes((prev) =>
      prev.filter((url) => url !== trimmed)
    );
    setNewMediaUrl('');
    setHasUnsavedChanges(true);
  };

  const handleMediaFiles = async (
    event: ChangeEvent<HTMLInputElement>
  ) => {
    const target = event.target;
    const files = target.files;
    if (!files || files.length === 0) {
      return;
    }
    if (!selectedOrgId) {
      setOrgActionAttempted(true);
      setError('Please select an organization first.');
      target.value = '';
      return;
    }
    setIsProcessingMedia(true);
    setError('');
    setSuccessMessage('');
    try {
      const selectedFiles = Array.from(files);
      const validFiles = selectedFiles.filter((file) =>
        file.type.startsWith('image/')
      );
      if (validFiles.length === 0) {
        setError('Only image files can be uploaded.');
        return;
      }

      const results = await Promise.allSettled(
        validFiles.map((file) => uploadMediaFile(selectedOrgId, file))
      );
      const uploadedUrls = results
        .filter(
          (result): result is PromiseFulfilledResult<string> =>
            result.status === 'fulfilled'
        )
        .map((result) => result.value);

      if (uploadedUrls.length > 0) {
        setMediaUrls((prev) =>
          normalizeMediaUrls([...prev, ...uploadedUrls])
        );
        setUploadedMediaUrls((prev) =>
          normalizeMediaUrls([...prev, ...uploadedUrls])
        );
        setHasUnsavedChanges(true);
      }

      if (results.some((result) => result.status === 'rejected')) {
        setError('Some uploads failed. Please retry.');
      }
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Unable to upload selected media files.';
      setError(message);
    } finally {
      setIsProcessingMedia(false);
      target.value = '';
    }
  };

  const removeMediaAt = (index: number) => {
    const removedUrl = mediaUrls[index];
    setMediaUrls((prev) => {
      const nextMedia = [...prev];
      nextMedia.splice(index, 1);
      return nextMedia;
    });
    if (removedUrl && removedUrl === logoMediaUrl) {
      setLogoMediaUrl(null);
    }
    if (removedUrl && selectedOrgId && isManagedMediaUrl(removedUrl)) {
      setPendingMediaDeletes((prev) =>
        normalizeMediaUrls([...prev, removedUrl])
      );
    }
    setHasUnsavedChanges(true);
  };

  const handleSelectLogo = (url: string) => {
    setLogoMediaUrl(url);
    setHasUnsavedChanges(true);
  };

  const moveMediaTo = (fromIndex: number, toIndex: number) => {
    setMediaUrls((prev) => reorderMediaUrls(prev, fromIndex, toIndex));
    setHasUnsavedChanges(true);
  };

  const handleDragStart = (
    event: DragEvent<HTMLButtonElement>,
    index: number
  ) => {
    if (isMediaBusy) {
      return;
    }
    setDragIndex(index);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(index));
  };

  const handleDragOver = (
    event: DragEvent<HTMLDivElement>,
    index: number
  ) => {
    if (isMediaBusy) {
      return;
    }
    event.preventDefault();
    setDragOverIndex(index);
  };

  const handleDrop = (
    event: DragEvent<HTMLDivElement>,
    index: number
  ) => {
    if (isMediaBusy) {
      return;
    }
    event.preventDefault();
    const raw = event.dataTransfer.getData('text/plain');
    const fromIndex = dragIndex !== null ? dragIndex : Number(raw);
    if (Number.isNaN(fromIndex) || fromIndex === index) {
      setDragIndex(null);
      setDragOverIndex(null);
      return;
    }
    setMediaUrls((prev) => reorderMediaUrls(prev, fromIndex, index));
    setHasUnsavedChanges(true);
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const handleDragEnd = () => {
    setDragIndex(null);
    setDragOverIndex(null);
  };

  const flushMediaDeletes = async (
    organizationId: string,
    currentMediaUrls: string[]
  ) => {
    if (pendingMediaDeletes.length === 0) {
      return;
    }

    const remaining = new Set(currentMediaUrls);
    const deletions = pendingMediaDeletes.filter(
      (url) => !remaining.has(url)
    );
    const managedDeletes = deletions.filter(isManagedMediaUrl);
    if (managedDeletes.length === 0) {
      setPendingMediaDeletes([]);
      return;
    }

    try {
      await Promise.all(
        managedDeletes.map((url) =>
          deleteOrganizationMedia(organizationId, { media_url: url })
        )
      );
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Saved media, but failed to delete some old files.';
      setError(message);
    } finally {
      setPendingMediaDeletes([]);
    }
  };

  const handleSave = async () => {
    if (!selectedOrgId || !selectedOrganization) {
      setOrgActionAttempted(true);
      setError('Please select an organization first.');
      return;
    }
    if (isProcessingMedia) {
      setError('Please wait for media processing to finish.');
      return;
    }
    setIsSaving(true);
    setError('');
    setSuccessMessage('');
    try {
      const normalizedUrls = normalizeMediaUrls(mediaUrls);
      const normalizedLogo =
        logoMediaUrl && normalizedUrls.includes(logoMediaUrl)
          ? logoMediaUrl
          : null;
      const payload = {
        name: selectedOrganization.name,
        description: selectedOrganization.description ?? null,
        manager_id: selectedOrganization.manager_id,
        media_urls: normalizedUrls,
        logo_media_url: normalizedLogo,
      };

      const updated = await updateResource<typeof payload, Organization>(
        'organizations',
        selectedOrgId,
        payload
      );

      // Update the organizations list with updated media_urls
      setOrganizations((prev) =>
        prev.map((org) => (org.id === selectedOrgId ? updated : org))
      );
      setLogoMediaUrl(updated.logo_media_url ?? null);

      await flushMediaDeletes(selectedOrgId, normalizedUrls);

      setUploadedMediaUrls([]);
      setHasUnsavedChanges(false);
      setSuccessMessage('Media saved successfully.');
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : 'Unable to save media.';
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancelChanges = async () => {
    if (!selectedOrgId) {
      return;
    }

    // Clean up uploaded media that haven't been saved
    if (uploadedMediaUrls.length > 0) {
      setIsProcessingMedia(true);
      try {
        await Promise.all(
          uploadedMediaUrls.map((url) =>
            deleteOrganizationMedia(selectedOrgId, { media_url: url })
          )
        );
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : 'Unable to clean up uploaded media.';
        setError(message);
      } finally {
        setIsProcessingMedia(false);
      }
    }

    // Reset to original state
    const org = organizations.find((o) => o.id === selectedOrgId);
    const nextMediaUrls = org?.media_urls ?? [];
    setMediaUrls(nextMediaUrls);
    setLogoMediaUrl(
      resolveLogoMediaUrl(nextMediaUrls, org?.logo_media_url)
    );
    setPendingMediaDeletes([]);
    setUploadedMediaUrls([]);
    setHasUnsavedChanges(false);
    setSuccessMessage('');
    setDragIndex(null);
    setDragOverIndex(null);
  };

  return (
    <div className='space-y-6'>
      <h2 className='sr-only'>Organization Media</h2>
      {error && (
        <StatusBanner variant='error' title='Error'>
          {error}
        </StatusBanner>
      )}
      {successMessage && (
        <StatusBanner variant='success' title='Success'>
          {successMessage}
        </StatusBanner>
      )}
      <AdminFilterBar>
        <AdminFilterField
          label={
            <>
              Organization <span className='ml-1'>{requiredIndicator}</span>
            </>
          }
          htmlFor='org-select'
        >
          <Select
            id='org-select'
            value={selectedOrgId}
            onChange={(event) => {
              void handleSelectOrganization(event.target.value);
            }}
            disabled={isLoadingOrgs || isMediaBusy || isSingleOrgManager}
            className={showOrgError ? errorInputClassName : ''}
            aria-invalid={showOrgError || undefined}
          >
            <option value=''>
              {isLoadingOrgs
                ? 'Loading organizations...'
                : 'Select an organization'}
            </option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </Select>
          {showOrgError ? (
            <p className='text-xs text-red-600'>{orgErrorMessage}</p>
          ) : null}
        </AdminFilterField>
      </AdminFilterBar>

      {selectedOrgId && (
        <Card>
          <AdminEditorPanel
            actions={
              <>
                <Button
                  type='button'
                  onClick={() => {
                    void handleSave();
                  }}
                  disabled={isProcessingMedia || !hasUnsavedChanges}
                  loading={isSaving}
                  loadingLabel='Saving…'
                  className='w-full sm:w-auto'
                >
                  Save media
                </Button>
                {hasUnsavedChanges && (
                  <Button
                    type='button'
                    variant='secondary'
                    onClick={() => void handleCancelChanges()}
                    disabled={isMediaBusy}
                    className='w-full sm:w-auto'
                  >
                    Cancel changes
                  </Button>
                )}
              </>
            }
          >
            <p className='text-sm text-slate-600'>
              Add or remove media for{' '}
              {selectedOrganization?.name ?? 'this organization'}.
            </p>
            <div className='flex flex-col gap-2 sm:flex-row'>
              <Input
                id='media-url'
                type='url'
                placeholder='https://example.com/photo.jpg'
                value={newMediaUrl}
                onChange={(event) => setNewMediaUrl(event.target.value)}
                disabled={isMediaBusy}
              />
              <Button
                type='button'
                variant='secondary'
                onClick={handleAddMediaUrl}
                disabled={isMediaBusy || !newMediaUrl.trim()}
                title='Add URL'
              >
                <PlusIcon className='h-4 w-4' />
              </Button>
            </div>
            <div className='flex flex-col gap-2 sm:flex-row sm:items-center'>
              <input
                id='media-upload'
                ref={fileInputRef}
                type='file'
                accept='image/*'
                multiple
                onChange={handleMediaFiles}
                disabled={isMediaBusy}
                aria-label='Upload media files'
                className='sr-only'
              />
              <Button
                type='button'
                variant='secondary'
                onClick={() => fileInputRef.current?.click()}
                disabled={isSaving}
                loading={isProcessingMedia}
                loadingLabel='Uploading…'
              >
                Choose files
              </Button>
              <p className='text-xs text-slate-500 sm:self-center'>
                Upload files or add URLs. Drag or use arrows to reorder.
                Select a logo, then save to apply changes.
              </p>
            </div>

            {mediaUrls.length > 0 ? (
              // Exception: image ordering stays a grid, not a record table.
              <MediaGrid
                mediaUrls={mediaUrls}
                logoMediaUrl={logoMediaUrl}
                isMediaBusy={isMediaBusy}
                dragIndex={dragIndex}
                dragOverIndex={dragOverIndex}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onSelectLogo={handleSelectLogo}
                onMoveMedia={moveMediaTo}
                onRemoveMedia={removeMediaAt}
              />
            ) : (
              <p className='text-sm text-slate-500'>
                No media added yet. Upload files or add URLs above.
              </p>
            )}
          </AdminEditorPanel>
        </Card>
      )}

      {!selectedOrgId && !isLoadingOrgs && organizations.length > 0 && (
        <Card>
          <p className='text-base font-semibold text-slate-900'>
            Select an organization
          </p>
          <p className='mt-1 text-sm text-slate-600'>
            Choose an organization from the dropdown above to manage its media.
          </p>
          <p className='mt-3 text-sm text-slate-600'>
            You can upload images or add media URLs to any organization.
            Media is saved when you click the &ldquo;Save media&rdquo;
            button.
          </p>
        </Card>
      )}

      {!selectedOrgId && !isLoadingOrgs && organizations.length === 0 && (
        <Card>
          <p className='text-base font-semibold text-slate-900'>
            No organizations found
          </p>
          <p className='mt-1 text-sm text-slate-600'>
            Create an organization first to manage its media.
          </p>
          <p className='mt-3 text-sm text-slate-600'>
            Go to the Organizations section to create a new organization, then
            return here to add media.
          </p>
        </Card>
      )}
      {confirmDialog}
    </div>
  );
}
