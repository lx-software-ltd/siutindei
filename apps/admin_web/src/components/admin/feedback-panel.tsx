'use client';

import { useEffect, useMemo, useState } from 'react';

import { useExhaustPages } from '../../hooks/use-exhaust-pages';
import { useResourceEditor } from '../../hooks/use-resource-editor';
import { ApiError, listResource } from '../../lib/api-client';
import { formatDate } from '../../lib/date-utils';
import type {
  FeedbackLabel,
  Organization,
  OrganizationFeedback,
} from '../../types/admin';
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
import {
  deleteRowActions,
  ResourceTableShell,
} from '../ui/resource-table-shell';
import { Select } from '../ui/select';
import { StarRating } from '../ui/star-rating';
import { Textarea } from '../ui/textarea';
import { StatusBanner } from '../status-banner';

interface FeedbackFormState {
  organization_id: string;
  submitter_id: string;
  submitter_email: string;
  stars: number;
  label_ids: string[];
  description: string;
  source_ticket_id: string;
}

const emptyForm: FeedbackFormState = {
  organization_id: '',
  submitter_id: '',
  submitter_email: '',
  stars: 1,
  label_ids: [],
  description: '',
  source_ticket_id: '',
};

function itemToForm(item: OrganizationFeedback): FeedbackFormState {
  return {
    organization_id: item.organization_id ?? '',
    submitter_id: item.submitter_id ?? '',
    submitter_email: item.submitter_email ?? '',
    stars: item.stars !== undefined ? item.stars : 1,
    label_ids: item.label_ids ?? [],
    description: item.description ?? '',
    source_ticket_id: item.source_ticket_id ?? '',
  };
}

export function FeedbackPanel() {
  const panel = useResourceEditor<OrganizationFeedback, FeedbackFormState>({
    resource: 'organization-feedback',
    mode: 'admin',
    emptyForm,
    itemToForm,
    paramName: 'feedback',
    noun: 'feedback',
  });

  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [labels, setLabels] = useState<FeedbackLabel[]>([]);
  const [lookupError, setLookupError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  useExhaustPages(Boolean(searchQuery.trim()), {
    hasMore: panel.hasMore,
    isLoading: panel.isLoading,
    isLoadingMore: panel.isLoadingMore,
    error: panel.listError,
    loadMore: panel.loadMore,
  });

  useEffect(() => {
    const loadLookups = async () => {
      setLookupError('');
      try {
        const [orgResponse, labelResponse] = await Promise.all([
          listResource<Organization>('organizations'),
          listResource<FeedbackLabel>('feedback-labels'),
        ]);
        setOrganizations(orgResponse.items);
        setLabels(labelResponse.items);
      } catch (err) {
        const message =
          err instanceof ApiError
            ? err.message
            : 'Failed to load feedback lookups.';
        setLookupError(message);
      }
    };
    loadLookups();
  }, []);

  const labelNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const label of labels) {
      map.set(label.id, label.name);
    }
    return map;
  }, [labels]);

  const toggleLabel = (labelId: string) => {
    panel.setFormState((prev) => {
      const hasLabel = prev.label_ids.includes(labelId);
      return {
        ...prev,
        label_ids: hasLabel
          ? prev.label_ids.filter((id) => id !== labelId)
          : [...prev.label_ids, labelId],
      };
    });
  };

  const validate = () => {
    if (!panel.formState.organization_id) {
      return 'Select an organization.';
    }
    const stars = panel.formState.stars;
    if (!Number.isInteger(stars) || stars < 0 || stars > 5) {
      return 'Stars must be a whole number between 0 and 5.';
    }
    return null;
  };

  const formToPayload = (form: FeedbackFormState) => ({
    organization_id: form.organization_id,
    submitter_id: form.submitter_id.trim() || undefined,
    submitter_email: form.submitter_email.trim() || undefined,
    stars: form.stars,
    label_ids: form.label_ids,
    description: form.description.trim() || undefined,
    source_ticket_id: form.source_ticket_id.trim() || undefined,
  });

  const handleSubmit = () => panel.handleSubmit(formToPayload, validate);

  const labelNames = (item: OrganizationFeedback) =>
    item.label_ids?.map((id) => labelNameById.get(id) || id) ?? [];

  const filteredItems = panel.items.filter((item) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const names = labelNames(item).join(' ').toLowerCase();
    return (
      (item.organization_name || item.organization_id)
        .toLowerCase()
        .includes(query) ||
      `${item.stars}`.includes(query) ||
      names.includes(query) ||
      (item.submitter_email || '').toLowerCase().includes(query) ||
      (item.submitter_id || '').toLowerCase().includes(query) ||
      (item.description || '').toLowerCase().includes(query)
    );
  });

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
        <div className='sm:col-span-2'>
          <Label htmlFor='feedback-organization'>Organization</Label>
          <Select
            id='feedback-organization'
            value={panel.formState.organization_id}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                organization_id: e.target.value,
              }))
            }
          >
            <option value=''>Select organization...</option>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor='feedback-stars'>Stars</Label>
          <div className='mt-2 flex items-center gap-2'>
            <StarRating
              value={panel.formState.stars}
              onChange={(value) =>
                panel.setFormState((prev) => ({
                  ...prev,
                  stars: value,
                }))
              }
            />
            <span className='text-sm text-slate-500'>
              {panel.formState.stars}/5
            </span>
          </div>
        </div>
        <div>
          <Label htmlFor='feedback-ticket-id'>Source Ticket ID</Label>
          <Input
            id='feedback-ticket-id'
            type='text'
            value={panel.formState.source_ticket_id}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                source_ticket_id: e.target.value,
              }))
            }
          />
        </div>
        <div>
          <Label htmlFor='feedback-submit-id'>Submitter ID</Label>
          <Input
            id='feedback-submit-id'
            type='text'
            value={panel.formState.submitter_id}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                submitter_id: e.target.value,
              }))
            }
          />
        </div>
        <div>
          <Label htmlFor='feedback-submit-email'>Submitter Email</Label>
          <Input
            id='feedback-submit-email'
            type='email'
            value={panel.formState.submitter_email}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                submitter_email: e.target.value,
              }))
            }
          />
        </div>
        <div className='sm:col-span-2'>
          <Label>Labels</Label>
          {labels.length === 0 ? (
            <p className='text-sm text-slate-500'>
              No feedback labels available.
            </p>
          ) : (
            <div className='mt-2 flex flex-wrap gap-2'>
              {labels.map((label) => {
                const isSelected = panel.formState.label_ids.includes(
                  label.id
                );
                return (
                  <button
                    key={label.id}
                    type='button'
                    onClick={() => toggleLabel(label.id)}
                    className={`rounded-full border px-3 py-1 text-sm ${
                      isSelected
                        ? 'border-slate-900 bg-slate-900 text-white'
                        : 'border-slate-200 bg-white text-slate-600'
                    }`}
                  >
                    {label.name}
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className='sm:col-span-2'>
          <Label htmlFor='feedback-description'>Description</Label>
          <Textarea
            id='feedback-description'
            rows={3}
            value={panel.formState.description}
            onChange={(e) =>
              panel.setFormState((prev) => ({
                ...prev,
                description: e.target.value,
              }))
            }
          />
        </div>
      </AdminFieldGrid>
    </AdminEditorPanel>
  );

  return (
    <>
      <ResourceTableShell
        ariaLabel='Organization feedback'
        rows={filteredItems}
        getLabel={(item) =>
          item.organization_name || item.organization_id || 'Feedback'
        }
        middleColumnCount={5}
        isLoading={panel.isLoading}
        isLoadingMore={panel.isLoadingMore}
        hasMore={panel.hasMore}
        onLoadMore={panel.loadMore}
        error={panel.listError}
        emptyLabel={
          searchQuery.trim()
            ? 'No feedback matches your search.'
            : 'No feedback entries found.'
        }
        isExpanded={panel.isExpanded}
        onToggle={panel.toggle}
        isDraftOpen={panel.isDraftOpen}
        draftLabel='New feedback'
        onToggleDraft={panel.collapse}
        detail={detail}
        toolbar={
          lookupError ? (
            <StatusBanner variant='error' title='Lookups'>
              {lookupError}
            </StatusBanner>
          ) : null
        }
        filters={
          <AdminFilterBar
            trailing={
              panel.canCreate ? (
                <AdminCreateButton
                  label='New feedback'
                  active={panel.isDraftOpen}
                  onClick={panel.openDraft}
                />
              ) : null
            }
          >
            <AdminFilterField label='Search' htmlFor='feedback-search'>
              <Input
                id='feedback-search'
                placeholder='Search feedback...'
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </AdminFilterField>
          </AdminFilterBar>
        }
        head={
          <>
            <AdminDataTableHeadCell>Organization</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>
              Stars
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Labels
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Submitter
            </AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>
              Submitted
            </AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => {
          const names = labelNames(item);
          return (
            <>
              <AdminDataTableCell>
                {item.organization_name || item.organization_id}
                <AdminDataTableCellMeta until='secondary'>
                  {item.stars}
                </AdminDataTableCellMeta>
              </AdminDataTableCell>
              <AdminDataTableCell priority='secondary'>
                {item.stars}
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                {names.length ? names.join(', ') : '—'}
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                {item.submitter_email || item.submitter_id || '—'}
              </AdminDataTableCell>
              <AdminDataTableCell priority='tertiary'>
                {formatDate(item.created_at)}
              </AdminDataTableCell>
            </>
          );
        }}
        renderActions={(item) =>
          deleteRowActions(() => panel.handleDelete(item))
        }
      />
      {panel.confirmDialog}
    </>
  );
}
