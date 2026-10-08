export type StatusBadgeTone =
  | 'green'
  | 'yellow'
  | 'red'
  | 'slate'
  | 'blue'
  | 'purple'
  | 'amber';

const toneClass: Record<StatusBadgeTone, string> = {
  green: 'bg-green-100 text-green-800',
  yellow: 'bg-yellow-100 text-yellow-800',
  red: 'bg-red-100 text-red-800',
  slate: 'bg-slate-200 text-slate-600',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
  amber: 'bg-amber-100 text-amber-800',
};

const statusToneByValue: Record<string, StatusBadgeTone> = {
  approved: 'green',
  rejected: 'red',
  pending_review: 'yellow',
  'pending review': 'yellow',
  operational: 'green',
  closed_temporarily: 'yellow',
  'closed temporarily': 'yellow',
  closed_permanently: 'red',
  'closed permanently': 'red',
  hidden: 'slate',
  active: 'green',
  revoked: 'red',
  expired: 'slate',
};

export interface StatusBadgeProps {
  status: string;
  /** Overrides the tone inferred from `status`. */
  tone?: StatusBadgeTone;
  /** Visible text. Defaults to the normalized status. */
  label?: string;
}

export function StatusBadge({ status, tone, label }: StatusBadgeProps) {
  const normalizedStatus = status.trim().toLowerCase();
  const resolvedTone = tone ?? statusToneByValue[normalizedStatus] ?? 'yellow';
  const text = label ?? (normalizedStatus || 'pending');

  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        label ? null : 'capitalize',
        toneClass[resolvedTone],
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {text}
    </span>
  );
}
