'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import { useEntityPanelEditorShell } from '@/hooks/use-entity-panel-editor-shell';
import { usePaginatedList } from '@/hooks/use-paginated-list';
import { ApiError, listResource } from '@/lib/api-client';
import { listCognitoUsers } from '@/lib/api-client-cognito';
import {
  listTickets,
  reviewTicket,
  type ReviewTicketPayload,
  type Ticket,
  type TicketType,
} from '@/lib/api-client-tickets';
import { adminQueryKeys } from '@/lib/admin-query-keys';
import { formatDateTime } from '@/lib/date-utils';
import type { FeedbackLabel, Organization } from '@/types/admin';
import { StatusBanner } from '@/components/status-banner';
import {
  AdminDataTableCell,
  AdminDataTableCellMeta,
  AdminDataTableHeadCell,
} from '@/components/ui/admin-data-table';
import { AdminDiscardChangesDialog } from '@/components/ui/admin-discard-changes-dialog';
import { AdminEditorPanel } from '@/components/ui/admin-editor-panel';
import { AdminField, AdminFieldGrid } from '@/components/ui/admin-field-grid';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ResourceTableShell, rowActions } from '@/components/ui/resource-table-shell';
import { Select } from '@/components/ui/select';
import { StatusBadge } from '@/components/ui/status-badge';
import { Textarea } from '@/components/ui/textarea';

type OrganizationMode = 'existing' | 'new';

interface ReviewFormState {
  adminNotes: string;
  createOrg: boolean;
  organizationMode: OrganizationMode;
  selectedOrgId: string;
  orgTouched: boolean;
  hasSubmitted: boolean;
}

const emptyReviewForm: ReviewFormState = {
  adminNotes: '',
  createOrg: true,
  organizationMode: 'new',
  selectedOrgId: '',
  orgTouched: false,
  hasSubmitted: false,
};

const TICKET_TYPE_LABELS: Record<TicketType, string> = {
  access_request: 'Access Request',
  organization_suggestion: 'Suggestion',
  organization_feedback: 'Feedback',
};

const TICKET_TYPE_COLORS: Record<TicketType, string> = {
  access_request: 'bg-blue-100 text-blue-800',
  organization_suggestion: 'bg-purple-100 text-purple-800',
  organization_feedback: 'bg-amber-100 text-amber-800',
};

function TicketTypeBadge({ type }: { type: TicketType }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TICKET_TYPE_COLORS[type]}`}
    >
      {TICKET_TYPE_LABELS[type]}
    </span>
  );
}

function ApproveIcon({ className }: { className?: string }) {
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
      <path d='M20 6 9 17l-5-5' />
    </svg>
  );
}

function RejectIcon({ className }: { className?: string }) {
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
      <path d='M18 6 6 18' />
      <path d='m6 6 12 12' />
    </svg>
  );
}

export function TicketsPanel() {
  const shell = useEntityPanelEditorShell({ paramName: 'ticket' });
  const { clearDirty, markDirty, selectedId } = shell;
  const [feedbackLabels, setFeedbackLabels] = useState<FeedbackLabel[]>([]);
  const [reviewForm, setReviewForm] = useState<ReviewFormState>(emptyReviewForm);
  const [reviewError, setReviewError] = useState('');
  const [reviewTargetId, setReviewTargetId] = useState<string | null>(null);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [managerEmails, setManagerEmails] = useState<Record<string, string>>({});
  const [isLoadingOrgs, setIsLoadingOrgs] = useState(false);
  const reviewTargetIdRef = useRef<string | null>(null);

  const list = usePaginatedList<Ticket, Record<string, never>>({
    queryKey: adminQueryKeys.tickets(),
    defaultFilters: {},
    errorPrefix: 'Failed to load tickets',
    fetcher: async ({ cursor }) => {
      const response = await listTickets(undefined, undefined, cursor ?? undefined);
      return {
        items: response.items,
        nextCursor: response.next_cursor ?? null,
        pendingCount: response.pending_count,
      };
    },
  });
  const pendingCount = list.pendingCount ?? 0;

  useEffect(() => {
    const loadLabels = async () => {
      try {
        const response = await listResource<FeedbackLabel>('feedback-labels');
        setFeedbackLabels(response.items);
      } catch {
        setFeedbackLabels([]);
      }
    };
    void loadLabels();
  }, []);

  useEffect(() => {
    setReviewForm(emptyReviewForm);
    clearDirty();
    if (reviewTargetIdRef.current !== selectedId) {
      setReviewError('');
    }
  }, [selectedId, clearDirty]);

  const selected = list.items.find((item) => item.id === selectedId) ?? null;
  const selectedTicketType = selected?.ticket_type;

  useEffect(() => {
    if (!selectedId || selectedTicketType !== 'access_request') {
      return;
    }
    let cancelled = false;
    const loadOrgs = async () => {
      setIsLoadingOrgs(true);
      try {
        const [orgsResponse, usersResponse] = await Promise.all([
          listResource<Organization>('organizations'),
          listCognitoUsers(),
        ]);
        if (cancelled) {
          return;
        }
        setOrganizations(orgsResponse.items);
        const emailMap: Record<string, string> = {};
        for (const user of usersResponse.items) {
          if (user.sub && user.email) {
            emailMap[user.sub] = user.email;
          }
        }
        setManagerEmails(emailMap);
      } catch {
        if (!cancelled) {
          setOrganizations([]);
        }
      } finally {
        if (!cancelled) {
          setIsLoadingOrgs(false);
        }
      }
    };
    void loadOrgs();
    return () => {
      cancelled = true;
    };
  }, [selectedId, selectedTicketType]);

  const labelNameById = useMemo(() => {
    const map: Record<string, string> = {};
    for (const label of feedbackLabels) {
      map[label.id] = label.name;
    }
    return map;
  }, [feedbackLabels]);

  const updateReviewForm = (patch: Partial<ReviewFormState>) => {
    markDirty();
    setReviewForm((prev) => ({ ...prev, ...patch }));
  };

  const submitReview = async (ticket: Ticket, action: 'approve' | 'reject') => {
    const usingForm = selectedId === ticket.id;
    const form = usingForm ? reviewForm : emptyReviewForm;
    reviewTargetIdRef.current = ticket.id;
    setReviewTargetId(ticket.id);

    if (
      ticket.ticket_type === 'access_request' &&
      action === 'approve' &&
      form.organizationMode === 'existing' &&
      !form.selectedOrgId
    ) {
      if (usingForm) {
        setReviewForm((prev) => ({ ...prev, orgTouched: true, hasSubmitted: true }));
      }
      setReviewError('Please select an organization');
      shell.expanded.expand(ticket.id);
      return;
    }

    setSubmittingId(ticket.id);
    setReviewError('');
    try {
      const payload: ReviewTicketPayload = {
        action,
        admin_notes: form.adminNotes.trim() || undefined,
      };
      if (action === 'approve') {
        if (ticket.ticket_type === 'access_request') {
          if (form.organizationMode === 'existing') {
            payload.organization_id = form.selectedOrgId;
          } else {
            payload.create_organization = true;
          }
        } else {
          payload.create_organization = form.createOrg;
        }
      }
      const response = await reviewTicket(ticket.id, payload);
      const updated = response.ticket;
      list.setItems((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item))
      );
      clearDirty();
      reviewTargetIdRef.current = null;
      shell.expanded.collapse();
      setReviewError('');
      await list.refetch();
    } catch (err) {
      const errorMessage = err instanceof ApiError ? err.message : 'Failed to process ticket';
      setReviewError(errorMessage);
      shell.expanded.expand(ticket.id);
    } finally {
      setSubmittingId(null);
    }
  };

  const detail = selected ? (
    <TicketDetail
      ticket={selected}
      form={reviewForm}
      reviewError={reviewTargetId === selected.id ? reviewError : ''}
      labelNameById={labelNameById}
      organizations={organizations}
      managerEmails={managerEmails}
      isLoadingOrgs={isLoadingOrgs}
      onChange={updateReviewForm}
    />
  ) : null;

  const showToolbarError = Boolean(reviewError && reviewTargetId !== selectedId);

  return (
    <>
      <ResourceTableShell
        ariaLabel='Tickets'
        rows={list.items}
        getLabel={(item) => item.ticket_id}
        middleColumnCount={6}
        isLoading={list.isLoading}
        isLoadingMore={list.isLoadingMore}
        hasMore={list.hasMore}
        onLoadMore={list.loadMore}
        error={list.error}
        emptyLabel='No tickets found.'
        isExpanded={shell.expanded.isExpanded}
        onToggle={shell.expanded.toggle}
        detail={detail}
        toolbar={
          pendingCount > 0 || showToolbarError ? (
            <div className='mb-3 space-y-3'>
              {pendingCount > 0 ? (
                <StatusBanner variant='info' title='Pending Review'>
                  {pendingCount} ticket{pendingCount !== 1 ? 's' : ''} awaiting review.
                </StatusBanner>
              ) : null}
              {showToolbarError ? (
                <StatusBanner variant='error' title='Error'>
                  {reviewError}
                </StatusBanner>
              ) : null}
            </div>
          ) : null
        }
        head={
          <>
            <AdminDataTableHeadCell>Organization</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Ticket ID</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Type</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Submitted By</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='secondary'>Status</AdminDataTableHeadCell>
            <AdminDataTableHeadCell priority='tertiary'>Submitted</AdminDataTableHeadCell>
          </>
        }
        renderCells={(item) => (
          <>
            <AdminDataTableCell>
              <span className='font-medium'>{item.organization_name}</span>
              <AdminDataTableCellMeta>
                {item.ticket_id}
                {item.suggested_district ? ` · ${item.suggested_district}` : ''}
              </AdminDataTableCellMeta>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <span className='font-mono text-xs text-slate-600'>{item.ticket_id}</span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <TicketTypeBadge type={item.ticket_type} />
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <span className='text-slate-600'>{item.submitter_email}</span>
            </AdminDataTableCell>
            <AdminDataTableCell priority='secondary'>
              <StatusBadge status={item.status} />
              {item.reviewed_at ? (
                <span className='mt-1 block text-xs text-slate-400'>
                  Reviewed {formatDateTime(item.reviewed_at)}
                </span>
              ) : null}
            </AdminDataTableCell>
            <AdminDataTableCell priority='tertiary'>
              <span className='text-slate-600'>{formatDateTime(item.created_at)}</span>
            </AdminDataTableCell>
          </>
        )}
        renderActions={(item) =>
          rowActions([
            {
              key: 'approve',
              label: 'Approve',
              tone: 'success',
              hidden: item.status !== 'pending',
              disabled: submittingId === item.id,
              icon: <ApproveIcon className='h-4 w-4' />,
              onClick: () => {
                void submitReview(item, 'approve');
              },
            },
            {
              key: 'reject',
              label: 'Reject',
              tone: 'danger',
              hidden: item.status !== 'pending',
              disabled: submittingId === item.id,
              icon: <RejectIcon className='h-4 w-4' />,
              onClick: () => {
                void submitReview(item, 'reject');
              },
            },
          ])
        }
      />
      <AdminDiscardChangesDialog prompt={shell.expanded.discardPrompt} />
    </>
  );
}

function TicketDetail({
  ticket,
  form,
  reviewError,
  labelNameById,
  organizations,
  managerEmails,
  isLoadingOrgs,
  onChange,
}: {
  ticket: Ticket;
  form: ReviewFormState;
  reviewError: string;
  labelNameById: Record<string, string>;
  organizations: Organization[];
  managerEmails: Record<string, string>;
  isLoadingOrgs: boolean;
  onChange: (patch: Partial<ReviewFormState>) => void;
}) {
  const fieldId = (name: string) => `ticket-${ticket.id}-${name}`;
  const isPending = ticket.status === 'pending';
  const isAccessRequest = ticket.ticket_type === 'access_request';
  const feedbackLabelNames = ticket.feedback_label_ids?.map((id) => labelNameById[id] || id) ?? [];
  const orgError =
    form.organizationMode === 'existing' && !form.selectedOrgId
      ? 'Choose an organization to continue.'
      : '';
  const showOrgError = Boolean(orgError && (form.hasSubmitted || form.orgTouched));

  return (
    <AdminEditorPanel
      status={
        reviewError ? (
          <StatusBanner variant='error' title='Error'>
            {reviewError}
          </StatusBanner>
        ) : null
      }
    >
      <AdminFieldGrid columns={2}>
        <AdminField label='Ticket ID' htmlFor={fieldId('ticket-id')}>
          <Input id={fieldId('ticket-id')} value={ticket.ticket_id} readOnly />
        </AdminField>
        <AdminField label='Type' htmlFor={fieldId('type')}>
          <Input id={fieldId('type')} value={TICKET_TYPE_LABELS[ticket.ticket_type]} readOnly />
        </AdminField>
        <AdminField label='Organization' htmlFor={fieldId('organization')}>
          <Input id={fieldId('organization')} value={ticket.organization_name} readOnly />
        </AdminField>
        <AdminField label='Submitted by' htmlFor={fieldId('submitter')}>
          <Input id={fieldId('submitter')} value={ticket.submitter_email} readOnly />
        </AdminField>
        <AdminField label='Status' htmlFor={fieldId('status')}>
          <Input id={fieldId('status')} value={ticket.status} readOnly />
        </AdminField>
        <AdminField label='Submitted' htmlFor={fieldId('submitted')}>
          <Input id={fieldId('submitted')} value={formatDateTime(ticket.created_at)} readOnly />
        </AdminField>
        {ticket.message ? (
          <AdminField label='Message' htmlFor={fieldId('message')} span='full'>
            <Textarea id={fieldId('message')} value={ticket.message} readOnly rows={3} />
          </AdminField>
        ) : null}
        {ticket.feedback_stars !== null && ticket.feedback_stars !== undefined ? (
          <AdminField label='Stars' htmlFor={fieldId('stars')}>
            <Input id={fieldId('stars')} value={String(ticket.feedback_stars)} readOnly />
          </AdminField>
        ) : null}
        {feedbackLabelNames.length > 0 ? (
          <AdminField label='Labels' htmlFor={fieldId('labels')} span='full'>
            <Input id={fieldId('labels')} value={feedbackLabelNames.join(', ')} readOnly />
          </AdminField>
        ) : null}
        {ticket.feedback_text ? (
          <AdminField label='Feedback' htmlFor={fieldId('feedback')} span='full'>
            <Textarea id={fieldId('feedback')} value={ticket.feedback_text} readOnly rows={3} />
          </AdminField>
        ) : null}
        {ticket.description ? (
          <AdminField label='Description' htmlFor={fieldId('description')} span='full'>
            <Textarea id={fieldId('description')} value={ticket.description} readOnly rows={3} />
          </AdminField>
        ) : null}
        {ticket.suggested_district ? (
          <AdminField label='District' htmlFor={fieldId('district')}>
            <Input id={fieldId('district')} value={ticket.suggested_district} readOnly />
          </AdminField>
        ) : null}
        {ticket.suggested_address ? (
          <AdminField label='Address' htmlFor={fieldId('address')} span='full'>
            <Input id={fieldId('address')} value={ticket.suggested_address} readOnly />
          </AdminField>
        ) : null}
        {!isPending && ticket.admin_notes ? (
          <AdminField label='Admin Notes' htmlFor={fieldId('notes-ro')} span='full'>
            <Textarea id={fieldId('notes-ro')} value={ticket.admin_notes} readOnly rows={3} />
          </AdminField>
        ) : null}
        {!isPending && ticket.reviewed_at ? (
          <AdminField label='Reviewed' htmlFor={fieldId('reviewed')}>
            <Input id={fieldId('reviewed')} value={formatDateTime(ticket.reviewed_at)} readOnly />
          </AdminField>
        ) : null}
      </AdminFieldGrid>

      {isPending && isAccessRequest ? (
        <div className='space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3'>
          <Label>Organization Assignment</Label>
          <p className='text-xs text-slate-500'>
            The requester will become the manager of the selected organization. This applies when
            you approve.
          </p>
          <div className='flex gap-2'>
            <label className='flex items-center gap-2'>
              <input
                type='radio'
                name={`org-mode-${ticket.id}`}
                value='new'
                checked={form.organizationMode === 'new'}
                onChange={() => {
                  onChange({
                    organizationMode: 'new',
                    selectedOrgId: '',
                    orgTouched: false,
                    hasSubmitted: false,
                  });
                }}
                className='h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-500'
              />
              <span className='text-sm'>Create new</span>
            </label>
            <label className='flex items-center gap-2'>
              <input
                type='radio'
                name={`org-mode-${ticket.id}`}
                value='existing'
                checked={form.organizationMode === 'existing'}
                onChange={() => {
                  onChange({ organizationMode: 'existing', orgTouched: false, hasSubmitted: false });
                }}
                className='h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-500'
              />
              <span className='text-sm'>Use existing</span>
            </label>
          </div>
          {form.organizationMode === 'new' ? (
            <div className='rounded border border-slate-200 bg-white p-2 text-sm'>
              <span className='text-slate-500'>New organization name:</span>{' '}
              <span className='font-medium'>{ticket.organization_name}</span>
            </div>
          ) : isLoadingOrgs ? (
            <p className='text-sm text-slate-500'>Loading organizations...</p>
          ) : organizations.length === 0 ? (
            <p className='text-sm text-slate-500'>No existing organizations available.</p>
          ) : (
            <AdminField
              label='Organization'
              htmlFor='org-select'
              required
              error={showOrgError ? orgError : undefined}
            >
              <Select
                id='org-select'
                value={form.selectedOrgId}
                onChange={(event) => {
                  onChange({ orgTouched: true, selectedOrgId: event.target.value });
                }}
                className={showOrgError ? 'border-red-500 focus:border-red-500 focus:ring-red-500' : ''}
                aria-invalid={showOrgError || undefined}
              >
                <option value=''>Select an organization...</option>
                {organizations.map((org) => {
                  const managerEmail = managerEmails[org.manager_id];
                  const displayText = managerEmail ? `${org.name} - ${managerEmail}` : org.name;
                  return (
                    <option key={org.id} value={org.id}>
                      {displayText}
                    </option>
                  );
                })}
              </Select>
            </AdminField>
          )}
        </div>
      ) : null}

      {isPending && !isAccessRequest ? (
        <label className='flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3'>
          <input
            type='checkbox'
            checked={form.createOrg}
            onChange={(event) => {
              onChange({ createOrg: event.target.checked });
            }}
            className='h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500'
          />
          <span className='text-sm'>Create organization from this suggestion</span>
        </label>
      ) : null}

      {isPending ? (
        <AdminField label='Admin Notes (Optional)' htmlFor='admin-notes'>
          <Textarea
            id='admin-notes'
            rows={3}
            value={form.adminNotes}
            onChange={(event) => {
              onChange({ adminNotes: event.target.value });
            }}
            placeholder='Add notes about your decision...'
          />
        </AdminField>
      ) : null}
    </AdminEditorPanel>
  );
}
