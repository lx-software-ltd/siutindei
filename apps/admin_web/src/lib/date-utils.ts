function toDate(value: string | null | undefined): Date | null {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date;
}

function padTwo(value: number): string {
  return String(value).padStart(2, '0');
}

function formatMonthDay(date: Date): string {
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

export function formatDate(dateString: string | null | undefined): string {
  const date = toDate(dateString);
  if (!date) {
    return '—';
  }
  return formatMonthDay(date);
}

export function formatDateTime(dateString: string | null | undefined): string {
  const date = toDate(dateString);
  if (!date) {
    return '—';
  }
  const hours24 = date.getHours();
  const period = hours24 >= 12 ? 'PM' : 'AM';
  const hours12 = hours24 % 12 || 12;
  return `${formatMonthDay(date)}, ${padTwo(hours12)}:${padTwo(date.getMinutes())} ${period}`;
}
