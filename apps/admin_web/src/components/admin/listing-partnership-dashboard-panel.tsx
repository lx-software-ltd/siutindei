'use client';

import { useListingPartnershipDashboard } from '../../hooks/use-listing-partnership-dashboard';
import { formatDateTime } from '../../lib/date-utils';
import type { DashboardRecentUpdate } from '../../lib/listing-partnership-dashboard';
import { StatusBanner } from '../status-banner';
import { Button } from '../ui/button';
import { Card } from '../ui/card';

interface ListingPartnershipDashboardPanelProps {
  onNavigateSection: (sectionKey: string) => void;
}

function MetricCard({
  label,
  value,
  hint,
  tone = 'default',
}: {
  label: string;
  value: number | string;
  hint?: string;
  tone?: 'default' | 'attention' | 'positive';
}) {
  const valueClassName =
    tone === 'attention'
      ? 'text-amber-700'
      : tone === 'positive'
        ? 'text-emerald-700'
        : 'text-slate-900';

  return (
    <div className='rounded-lg border border-slate-200 bg-slate-50 p-4'>
      <p className='text-xs font-medium uppercase tracking-wide text-slate-500'>
        {label}
      </p>
      <p className={`mt-2 text-3xl font-semibold tabular-nums ${valueClassName}`}>
        {value}
      </p>
      {hint && <p className='mt-2 text-xs text-slate-600'>{hint}</p>}
    </div>
  );
}

function updateKindLabel(update: DashboardRecentUpdate): string {
  if (update.kind === 'listing_status') {
    return 'Listing';
  }
  if (update.kind === 'partnership_ticket') {
    return 'Partnership';
  }
  return 'Organization';
}

export function ListingPartnershipDashboardPanel({
  onNavigateSection,
}: ListingPartnershipDashboardPanelProps) {
  const { metrics, recentUpdates, isLoading, error, reload } =
    useListingPartnershipDashboard();

  if (isLoading && !metrics) {
    return (
      <StatusBanner variant='info' title='Loading dashboard'>
        Gathering listing and vendor partnership metrics.
      </StatusBanner>
    );
  }

  return (
    <div className='space-y-6'>
      <div className='flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between'>
        <div>
          <h2 className='text-lg font-semibold sm:text-xl'>
            Listing &amp; vendor partnerships
          </h2>
          <p className='mt-1 text-sm text-slate-600'>
            Track public listings, pending vendor onboarding, and recent changes.
          </p>
        </div>
        <Button type='button' variant='secondary' onClick={() => reload()}>
          Refresh
        </Button>
      </div>

      {error && (
        <StatusBanner variant='error' title='Dashboard'>
          {error}
        </StatusBanner>
      )}

      {metrics && (
        <>
          <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-4'>
            <MetricCard
              label='Active listings'
              value={metrics.activeListings}
              hint={`${metrics.totalOrganizations} organizations total`}
              tone='positive'
            />
            <MetricCard
              label='Pending vendor partnerships'
              value={metrics.pendingPartnershipTickets}
              hint={`${metrics.partnershipTickets.access_request} access · ` +
                `${metrics.partnershipTickets.organization_suggestion} suggestions`}
              tone={
                metrics.pendingPartnershipTickets > 0 ? 'attention' : 'default'
              }
            />
            <MetricCard
              label='Active vendor API keys'
              value={metrics.activeVendorApiKeys}
              hint='Partner integrations currently enabled'
            />
            <MetricCard
              label='Listings without vendor key'
              value={metrics.activeListingsWithoutVendorKey}
              hint='Public listings missing an org-scoped API key'
              tone={
                metrics.activeListingsWithoutVendorKey > 0
                  ? 'attention'
                  : 'default'
              }
            />
          </div>

          <div className='grid gap-4 lg:grid-cols-2'>
            <Card
              title='Listing status breakdown'
              description='Counts by organization listing status.'
            >
              <ul className='space-y-2 text-sm text-slate-700'>
                <li className='flex justify-between gap-4'>
                  <span>Operational</span>
                  <span className='font-medium tabular-nums'>
                    {metrics.listingStatus.operational}
                  </span>
                </li>
                <li className='flex justify-between gap-4'>
                  <span>Temporarily closed</span>
                  <span className='font-medium tabular-nums'>
                    {metrics.listingStatus.closed_temporarily}
                  </span>
                </li>
                <li className='flex justify-between gap-4'>
                  <span>Closed permanently</span>
                  <span className='font-medium tabular-nums'>
                    {metrics.listingStatus.closed_permanently}
                  </span>
                </li>
                <li className='flex justify-between gap-4'>
                  <span>Hidden</span>
                  <span className='font-medium tabular-nums'>
                    {metrics.listingStatus.hidden}
                  </span>
                </li>
              </ul>
              <div className='mt-4'>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => onNavigateSection('organizations')}
                >
                  Review organizations
                </Button>
              </div>
            </Card>

            <Card
              title='Actionable next steps'
              description='Shortcuts for the ops team.'
            >
              <ul className='list-disc space-y-2 pl-5 text-sm text-slate-700'>
                {metrics.pendingPartnershipTickets > 0 ? (
                  <li>
                    {metrics.pendingPartnershipTickets} partnership ticket
                    {metrics.pendingPartnershipTickets === 1 ? '' : 's'} need
                    review.
                  </li>
                ) : (
                  <li>No pending vendor partnership tickets.</li>
                )}
                {metrics.activeListingsWithoutVendorKey > 0 ? (
                  <li>
                    {metrics.activeListingsWithoutVendorKey} active listing
                    {metrics.activeListingsWithoutVendorKey === 1
                      ? ''
                      : 's'}{' '}
                    lack an org-scoped vendor API key.
                  </li>
                ) : (
                  <li>All active listings have a vendor API key.</li>
                )}
                {metrics.listingStatus.hidden > 0 && (
                  <li>
                    {metrics.listingStatus.hidden} hidden listing
                    {metrics.listingStatus.hidden === 1 ? '' : 's'} may need a
                    publish check.
                  </li>
                )}
              </ul>
              <div className='mt-4 flex flex-wrap gap-2'>
                <Button
                  type='button'
                  onClick={() => onNavigateSection('tickets')}
                >
                  Open tickets
                </Button>
                <Button
                  type='button'
                  variant='secondary'
                  onClick={() => onNavigateSection('api-keys')}
                >
                  Manage API keys
                </Button>
              </div>
            </Card>
          </div>

          <Card
            title='Recent updates'
            description='Latest listing changes and partnership submissions.'
          >
            {recentUpdates.length === 0 ? (
              <p className='text-sm text-slate-600'>No recent updates yet.</p>
            ) : (
              <ul className='divide-y divide-slate-100'>
                {recentUpdates.map((update) => (
                  <li
                    key={update.id}
                    className='flex flex-col gap-1 py-3 sm:flex-row sm:items-center sm:justify-between'
                  >
                    <div>
                      <p className='text-sm font-medium text-slate-900'>
                        {update.title}
                      </p>
                      <p className='text-sm text-slate-600'>{update.detail}</p>
                    </div>
                    <div className='flex shrink-0 items-center gap-3 text-xs text-slate-500'>
                      <span className='rounded-full bg-slate-100 px-2 py-0.5 font-medium uppercase tracking-wide'>
                        {updateKindLabel(update)}
                      </span>
                      <time dateTime={update.occurredAt}>
                        {formatDateTime(update.occurredAt)}
                      </time>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
