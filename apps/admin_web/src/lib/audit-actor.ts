/** Partner writes store `api-key:<id>` in `audit_log.user_id`. */
const API_KEY_ACTOR_PREFIX = 'api-key:';

export interface AuditActor {
  kind: 'migration' | 'user' | 'key';
  text: string;
}

export function formatAuditActor(
  userId: string | null | undefined,
  emailById: Record<string, string>,
  keyNameById: Record<string, string> = {}
): AuditActor {
  if (!userId) {
    return { kind: 'migration', text: 'migration' };
  }
  if (userId.startsWith(API_KEY_ACTOR_PREFIX)) {
    const keyId = userId.slice(API_KEY_ACTOR_PREFIX.length);
    const name = keyNameById[keyId]?.trim();
    return { kind: 'key', text: name || '—' };
  }
  return { kind: 'user', text: emailById[userId] || '—' };
}
