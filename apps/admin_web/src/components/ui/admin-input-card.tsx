'use client';

import type { HTMLAttributes, ReactNode } from 'react';

import { AdminEditorPanel } from './admin-editor-panel';
import { Card } from './card';
import { hasContent } from './node-content';

export interface AdminInputCardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title: string;
  /** `h3` when this card sits under the page heading. */
  titleLevel?: 'h2' | 'h3';
  titleAccessory?: ReactNode;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
  status?: ReactNode;
  /** Rendered after the action bar. Import results use this slot. */
  footer?: ReactNode;
  className?: string;
}

/**
 * Page-level input card: required title, variable content, and an action
 * bar when there are actions. Login and dialog overlays stay on `Card`.
 * Expanded row editors stay on `AdminEditorPanel` inside the table card.
 */
export function AdminInputCard({
  title,
  titleLevel = 'h2',
  titleAccessory,
  description,
  children,
  actions,
  status,
  footer,
  className,
  ...rest
}: AdminInputCardProps) {
  const showActions = hasContent(actions);
  const showPanel = hasContent(children) || hasContent(status) || showActions;
  return (
    <Card
      title={title}
      titleLevel={titleLevel}
      titleAccessory={titleAccessory}
      description={description}
      className={className}
      {...rest}
    >
      {showPanel ? (
        <AdminEditorPanel
          actionRow={showActions}
          actions={showActions ? actions : undefined}
          status={status}
        >
          {children ?? null}
        </AdminEditorPanel>
      ) : null}
      {hasContent(footer) ? <div className='mt-4'>{footer}</div> : null}
    </Card>
  );
}
