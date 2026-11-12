/**
 * Actor ids written by the backend. `api-key:` matches
 * `userSub` in `api_key_authorizer.py`. `category-scan:` matches
 * `scan_apply.py`.
 */
const API_KEY_ACTOR_PREFIX = 'api-key:';

const JOB_ACTOR_LABELS: Record<string, string> = {
  'category-scan': 'category check',
};

export interface AuditActorUser {
  email: string;
  username?: string | null;
}

export type AuditActor =
  | { kind: 'system'; text: 'system' }
  | { kind: 'user'; text: string; username: string | null }
  | { kind: 'key'; text: string }
  | { kind: 'job'; text: string };

function jobLabel(prefix: string): string {
  return JOB_ACTOR_LABELS[prefix] ?? prefix.replaceAll('-', ' ');
}

export function formatAuditActor(
  userId: string | null | undefined,
  usersById: Record<string, AuditActorUser>,
  keyNameById: Record<string, string> = {}
): AuditActor {
  if (!userId) {
    return { kind: 'system', text: 'system' };
  }
  if (userId.startsWith(API_KEY_ACTOR_PREFIX)) {
    const keyId = userId.slice(API_KEY_ACTOR_PREFIX.length);
    const name = keyNameById[keyId]?.trim();
    return { kind: 'key', text: name || '—' };
  }
  const separator = userId.indexOf(':');
  if (separator > 0) {
    return { kind: 'job', text: jobLabel(userId.slice(0, separator)) };
  }
  const user = usersById[userId];
  return {
    kind: 'user',
    text: user?.email?.trim() || '—',
    username: user?.username?.trim() || null,
  };
}
