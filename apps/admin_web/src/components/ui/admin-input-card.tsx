'use client';

import type { HTMLAttributes, ReactNode } from 'react';

import { AdminEditorPanel } from './admin-editor-panel';
import { Card } from './card';

export interface AdminInputCardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title: string;
  titleAccessory?: ReactNode;
  description?: string;
  children?: ReactNode;
  actions?: ReactNode;
  status?: ReactNode;
  className?: string;
}

/**
 * Page-level input card: required title, variable content, and a bar that
 * always renders. Login and dialog overlays stay on `Card`. Expanded row
 * editors stay on `AdminEditorPanel` inside the table card.
 */
export function AdminInputCard({
  title,
  titleAccessory,
  description,
  children,
  actions,
  status,
  className,
  ...rest
}: AdminInputCardProps) {
  return (
    <Card
      title={title}
      titleAccessory={titleAccessory}
      description={description}
      className={className}
      {...rest}
    >
      <AdminEditorPanel actionRow actions={actions} status={status}>
        {children ?? null}
      </AdminEditorPanel>
    </Card>
  );
}
