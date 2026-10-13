export function formatAuditActor(
  userId: string | null | undefined,
  emailById: Record<string, string>
): string {
  if (!userId) {
    return 'migration';
  }
  return emailById[userId] || '—';
}
