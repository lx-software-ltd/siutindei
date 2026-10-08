import {
  createOrganizationMediaUpload,
  deleteOrganizationMedia,
} from '../../../lib/api-client-media';
import type { ApiMode } from '../../../lib/resource-api';

export interface MediaPanelProps {
  mode?: ApiMode;
}

export interface MediaPanelState {
  selectedOrgId: string;
  orgTouched: boolean;
  orgActionAttempted: boolean;
  isSaving: boolean;
  isProcessingMedia: boolean;
  error: string;
  successMessage: string;
  mediaUrls: string[];
  logoMediaUrl: string | null;
  newMediaUrl: string;
  pendingMediaDeletes: string[];
  uploadedMediaUrls: string[];
  hasUnsavedChanges: boolean;
  dragIndex: number | null;
  dragOverIndex: number | null;
}

export type MediaPanelAction =
  | {
      type: 'set-field';
      field: keyof MediaPanelState;
      value: unknown;
    }
  | {
      type: 'set-field-updater';
      field: keyof MediaPanelState;
      updater: (previous: unknown) => unknown;
    }
  | {
      type: 'patch';
      payload: Partial<MediaPanelState>;
    };

export const initialMediaPanelState: MediaPanelState = {
  selectedOrgId: '',
  orgTouched: false,
  orgActionAttempted: false,
  isSaving: false,
  isProcessingMedia: false,
  error: '',
  successMessage: '',
  mediaUrls: [],
  logoMediaUrl: null,
  newMediaUrl: '',
  pendingMediaDeletes: [],
  uploadedMediaUrls: [],
  hasUnsavedChanges: false,
  dragIndex: null,
  dragOverIndex: null,
};

export function mediaPanelReducer(
  state: MediaPanelState,
  action: MediaPanelAction
): MediaPanelState {
  switch (action.type) {
    case 'set-field':
      return {
        ...state,
        [action.field]: action.value,
      };
    case 'set-field-updater': {
      const previousValue = state[action.field];
      return {
        ...state,
        [action.field]: action.updater(previousValue),
      };
    }
    case 'patch':
      return {
        ...state,
        ...action.payload,
      };
    default:
      return state;
  }
}

export function normalizeMediaUrls(urls: string[]) {
  const cleaned = urls
    .map((url) => url.trim())
    .filter((url) => url.length > 0);
  return Array.from(new Set(cleaned));
}

export function reorderMediaUrls(
  urls: string[],
  fromIndex: number,
  toIndex: number
) {
  if (
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= urls.length ||
    toIndex >= urls.length ||
    fromIndex === toIndex
  ) {
    return urls;
  }
  const next = [...urls];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

export function resolveLogoMediaUrl(
  mediaUrls: string[],
  logoMediaUrl?: string | null
) {
  if (!logoMediaUrl) {
    return null;
  }
  return mediaUrls.includes(logoMediaUrl) ? logoMediaUrl : null;
}

export function isManagedMediaUrl(url: string) {
  return url.startsWith('http') && url.includes('amazonaws.com/');
}

export async function uploadMediaFile(
  organizationId: string,
  file: File
): Promise<string> {
  if (!file.type.startsWith('image/')) {
    throw new Error('Only image files are supported.');
  }

  const payload = {
    file_name: file.name,
    content_type: file.type,
  };
  const upload = await createOrganizationMediaUpload(organizationId, payload);

  const response = await fetch(upload.upload_url, {
    method: 'PUT',
    headers: {
      'Content-Type': file.type,
    },
    body: file,
  });

  if (!response.ok) {
    throw new Error('Failed to upload media.');
  }

  return upload.media_url;
}

/** Deletes uploads that were never written onto the organization. */
export function discardUnsavedMediaUploads(
  organizationId: string,
  urls: string[]
): void {
  const unique = normalizeMediaUrls(urls);
  if (!organizationId || unique.length === 0) {
    return;
  }
  void Promise.all(
    unique.map((url) =>
      deleteOrganizationMedia(organizationId, { media_url: url }).catch(
        () => undefined
      )
    )
  );
}
