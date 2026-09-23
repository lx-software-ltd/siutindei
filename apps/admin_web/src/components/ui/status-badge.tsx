interface StatusBadgeProps {
  status: string;
}

const statusColorClassByValue: Record<string, string> = {
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  pending_review: 'bg-yellow-100 text-yellow-800',
  'pending review': 'bg-yellow-100 text-yellow-800',
  operational: 'bg-green-100 text-green-800',
  closed_temporarily: 'bg-yellow-100 text-yellow-800',
  'closed temporarily': 'bg-yellow-100 text-yellow-800',
  closed_permanently: 'bg-red-100 text-red-800',
  'closed permanently': 'bg-red-100 text-red-800',
  hidden: 'bg-slate-200 text-slate-600',
  active: 'bg-green-100 text-green-800',
  revoked: 'bg-red-100 text-red-800',
  expired: 'bg-slate-200 text-slate-600',
};

export function StatusBadge({ status }: StatusBadgeProps) {
  const normalizedStatus = status.trim().toLowerCase();
  const colorClass =
    statusColorClassByValue[normalizedStatus] ??
    'bg-yellow-100 text-yellow-800';

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${colorClass}`}
    >
      {normalizedStatus || 'pending'}
    </span>
  );
}
