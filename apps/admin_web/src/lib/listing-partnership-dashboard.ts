import type { ApiKey, Organization } from '../types/admin';
import type { Ticket, TicketType } from './api-client-tickets';

export const PUBLIC_LISTING_STATUSES = new Set([
  'operational',
  'closed_temporarily',
]);

export type OrganizationListingStatus =
  | 'operational'
  | 'closed_temporarily'
  | 'closed_permanently'
  | 'hidden';

export interface ListingStatusBreakdown {
  operational: number;
  closed_temporarily: number;
  closed_permanently: number;
  hidden: number;
  unknown: number;
}

export interface PartnershipTicketBreakdown {
  access_request: number;
  organization_suggestion: number;
  organization_feedback: number;
  other: number;
}

export interface ListingPartnershipMetrics {
  totalOrganizations: number;
  activeListings: number;
  listingStatus: ListingStatusBreakdown;
  pendingPartnershipTickets: number;
  partnershipTickets: PartnershipTicketBreakdown;
  activeVendorApiKeys: number;
  activeListingsWithoutVendorKey: number;
}

export type DashboardUpdateKind =
  | 'listing_status'
  | 'organization'
  | 'partnership_ticket';

export interface DashboardRecentUpdate {
  id: string;
  kind: DashboardUpdateKind;
  title: string;
  detail: string;
  occurredAt: string;
  ticketType?: TicketType;
  organizationId?: string;
}

function normalizeOrgStatus(
  status: Organization['status'] | undefined
): OrganizationListingStatus | 'unknown' {
  if (!status) {
    return 'unknown';
  }
  if (
    status === 'operational' ||
    status === 'closed_temporarily' ||
    status === 'closed_permanently' ||
    status === 'hidden'
  ) {
    return status;
  }
  return 'unknown';
}

function isActiveApiKey(key: ApiKey, now = Date.now()): boolean {
  if (key.status !== 'active') {
    return false;
  }
  if (key.revoked_at) {
    return false;
  }
  if (key.expires_at) {
    const expiresAt = new Date(key.expires_at).getTime();
    if (!Number.isNaN(expiresAt) && expiresAt <= now) {
      return false;
    }
  }
  return true;
}

export function buildListingPartnershipMetrics(
  organizations: Organization[],
  pendingTickets: Ticket[],
  apiKeys: ApiKey[]
): ListingPartnershipMetrics {
  const listingStatus: ListingStatusBreakdown = {
    operational: 0,
    closed_temporarily: 0,
    closed_permanently: 0,
    hidden: 0,
    unknown: 0,
  };

  let activeListings = 0;
  for (const org of organizations) {
    const status = normalizeOrgStatus(org.status);
    listingStatus[status] += 1;
    if (PUBLIC_LISTING_STATUSES.has(status)) {
      activeListings += 1;
    }
  }

  const partnershipTickets: PartnershipTicketBreakdown = {
    access_request: 0,
    organization_suggestion: 0,
    organization_feedback: 0,
    other: 0,
  };

  for (const ticket of pendingTickets) {
    if (ticket.ticket_type === 'access_request') {
      partnershipTickets.access_request += 1;
    } else if (ticket.ticket_type === 'organization_suggestion') {
      partnershipTickets.organization_suggestion += 1;
    } else if (ticket.ticket_type === 'organization_feedback') {
      partnershipTickets.organization_feedback += 1;
    } else {
      partnershipTickets.other += 1;
    }
  }

  const pendingPartnershipTickets =
    partnershipTickets.access_request +
    partnershipTickets.organization_suggestion;

  const orgIdsWithActiveKey = new Set<string>();
  let activeVendorApiKeys = 0;
  for (const key of apiKeys) {
    if (!isActiveApiKey(key)) {
      continue;
    }
    activeVendorApiKeys += 1;
    if (key.org_id) {
      orgIdsWithActiveKey.add(key.org_id);
    }
  }

  let activeListingsWithoutVendorKey = 0;
  for (const org of organizations) {
    const status = normalizeOrgStatus(org.status);
    if (!PUBLIC_LISTING_STATUSES.has(status)) {
      continue;
    }
    if (!orgIdsWithActiveKey.has(org.id)) {
      activeListingsWithoutVendorKey += 1;
    }
  }

  return {
    totalOrganizations: organizations.length,
    activeListings,
    listingStatus,
    pendingPartnershipTickets,
    partnershipTickets,
    activeVendorApiKeys,
    activeListingsWithoutVendorKey,
  };
}

function ticketUpdateTitle(ticket: Ticket): string {
  if (ticket.ticket_type === 'access_request') {
    return 'Manager access request';
  }
  if (ticket.ticket_type === 'organization_suggestion') {
    return 'Place suggestion';
  }
  if (ticket.ticket_type === 'organization_feedback') {
    return 'Organization feedback';
  }
  return 'Ticket update';
}

function listingStatusLabel(status: OrganizationListingStatus | 'unknown') {
  switch (status) {
    case 'operational':
      return 'Operational';
    case 'closed_temporarily':
      return 'Temporarily closed';
    case 'closed_permanently':
      return 'Closed permanently';
    case 'hidden':
      return 'Hidden';
    default:
      return 'Unknown status';
  }
}

export function buildRecentUpdates(
  organizations: Organization[],
  pendingTickets: Ticket[],
  limit = 12
): DashboardRecentUpdate[] {
  const updates: DashboardRecentUpdate[] = [];

  for (const org of organizations) {
    if (org.status_changed_at) {
      const status = normalizeOrgStatus(org.status);
      updates.push({
        id: `org-status-${org.id}-${org.status_changed_at}`,
        kind: 'listing_status',
        title: org.name,
        detail: `Listing status: ${listingStatusLabel(status)}`,
        occurredAt: org.status_changed_at,
        organizationId: org.id,
      });
    }

    if (org.updated_at) {
      updates.push({
        id: `org-updated-${org.id}-${org.updated_at}`,
        kind: 'organization',
        title: org.name,
        detail: 'Organization profile updated',
        occurredAt: org.updated_at,
        organizationId: org.id,
      });
    }
  }

  for (const ticket of pendingTickets) {
    updates.push({
      id: `ticket-${ticket.id}`,
      kind: 'partnership_ticket',
      title: ticket.organization_name || ticketUpdateTitle(ticket),
      detail: `${ticketUpdateTitle(ticket)} awaiting review`,
      occurredAt: ticket.created_at,
      ticketType: ticket.ticket_type,
    });
  }

  updates.sort(
    (left, right) =>
      new Date(right.occurredAt).getTime() -
      new Date(left.occurredAt).getTime()
  );

  const seen = new Set<string>();
  const deduped: DashboardRecentUpdate[] = [];
  for (const update of updates) {
    if (seen.has(update.id)) {
      continue;
    }
    seen.add(update.id);
    deduped.push(update);
    if (deduped.length >= limit) {
      break;
    }
  }

  return deduped;
}
