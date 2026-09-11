'use client';

import type { ReactNode } from 'react';

import {
  trackGenerateLead,
  type AnalyticsItemFields,
  type LeadType,
} from '@/lib/analytics/data-layer';

interface TrackedWhatsappLinkProps {
  readonly href: string;
  readonly leadType: LeadType;
  readonly item?: AnalyticsItemFields;
  readonly locationId?: string;
  readonly activityId?: string;
  readonly className?: string;
  readonly target?: string;
  readonly rel?: string;
  readonly children: ReactNode;
}

export function TrackedWhatsappLink({
  href,
  leadType,
  item,
  locationId,
  activityId,
  className,
  target,
  rel,
  children,
}: TrackedWhatsappLinkProps) {
  function handleClick() {
    trackGenerateLead(leadType, item, { locationId, activityId });
  }

  return (
    <a
      href={href}
      className={className}
      target={target}
      rel={rel}
      onClick={handleClick}
    >
      {children}
    </a>
  );
}
