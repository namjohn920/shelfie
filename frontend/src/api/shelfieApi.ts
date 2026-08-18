import type { UploadResult } from '../types/api';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/+$/, '');

export class ShelfieApiError extends Error {}

type UploadablePhoto = {
  uri: string;
  fileName?: string | null;
  mimeType?: string;
};

function isUploadResult(value: unknown): value is UploadResult {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const result = value as Record<string, unknown>;
  return (
    result.status === 'received' &&
    typeof result.filename === 'string' &&
    typeof result.width === 'number' &&
    typeof result.height === 'number'
  );
}

function responseError(value: unknown): string | null {
  if (typeof value !== 'object' || value === null) {
    return null;
  }

  const error = (value as Record<string, unknown>).error;
  return typeof error === 'string' ? error : null;
}

function filenameFor(photo: UploadablePhoto): string {
  if (photo.fileName) {
    return photo.fileName;
  }

  const uriFilename = photo.uri.split('/').pop()?.split('?')[0];
  return uriFilename || 'bookshelf.jpg';
}

export async function analyzeBookshelfPhoto(
  selectedImage: UploadablePhoto,
): Promise<UploadResult> {
  if (!API_BASE_URL) {
    throw new ShelfieApiError(
      'The API URL is not configured. Set EXPO_PUBLIC_API_BASE_URL and restart Expo.',
    );
  }

  const formData = new FormData();
  const imagePart = {
    uri: selectedImage.uri,
    name: filenameFor(selectedImage),
    type: selectedImage.mimeType || 'image/jpeg',
  };
  // React Native accepts file descriptors here; the shared DOM type only
  // describes browser Blob values.
  formData.append('image', imagePart as unknown as Blob);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/analyze/`, {
      method: 'POST',
      body: formData,
    });
  } catch {
    throw new ShelfieApiError(
      'Shelfie could not reach the backend. Check that Django is running and both devices are on the same network.',
    );
  }

  let responseBody: unknown;
  try {
    responseBody = await response.json();
  } catch {
    throw new ShelfieApiError('The backend returned an unreadable response.');
  }

  if (!response.ok) {
    throw new ShelfieApiError(
      responseError(responseBody) ||
        `The upload failed with HTTP ${response.status}.`,
    );
  }

  if (!isUploadResult(responseBody)) {
    throw new ShelfieApiError('The backend returned an unexpected response.');
  }

  return responseBody;
}
