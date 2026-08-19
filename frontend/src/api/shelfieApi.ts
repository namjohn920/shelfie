import type {
  AnalyzeResult,
  AnalyzedBook,
  ClearLibraryResponse,
  CropThumbnail,
  LibraryBook,
  MatchCandidate,
  ReviewGroup,
  ReviewItem,
  ReviewVolumeBucket,
} from '../types/api';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/+$/, '');

export class ShelfieApiError extends Error {}

type UploadablePhoto = {
  uri: string;
  fileName?: string | null;
  mimeType?: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isMatchCandidate(value: unknown): value is MatchCandidate {
  if (!isRecord(value) || !isRecord(value.catalog)) {
    return false;
  }

  return (
    typeof value.catalog.catalog_id === 'string' &&
    typeof value.catalog.title === 'string' &&
    typeof value.catalog.author === 'string'
  );
}

function isNullableEnum(value: unknown, allowed: string[]): boolean {
  return value === null || allowed.includes(String(value));
}

function isAnalyzedBook(value: unknown): value is AnalyzedBook {
  if (!isRecord(value) || !isRecord(value.review)) {
    return false;
  }

  const validStatus = [
    'high_confidence',
    'review_required',
    'unmatched',
  ].includes(String(value.review.status));
  const validReasons =
    Array.isArray(value.review.reasons) &&
    value.review.reasons.every((reason) =>
      [
        'read_failed',
        'unreadable',
        'no_evidence',
        'no_candidate',
        'partial_read',
        'low_score',
        'small_margin',
        'candidate_not_reliable_enough_to_show',
        'non_book',
        'high_confidence',
      ].includes(String(reason)),
    );
  const validRead =
    value.read === null ||
    (isRecord(value.read) &&
      isNullableString(value.read.title) &&
      isNullableString(value.read.author) &&
      isNullableString(value.read.volume));
  const validMatch =
    value.match === null ||
    (isRecord(value.match) &&
      (value.match.combined_score === null ||
        typeof value.match.combined_score === 'number') &&
      (value.match.margin === null || typeof value.match.margin === 'number') &&
      (value.match.best_candidate === null ||
        isMatchCandidate(value.match.best_candidate)));

  return (
    typeof value.detection_index === 'number' &&
    typeof value.book_index === 'number' &&
    isNullableEnum(value.crop_type, [
      'single_book',
      'multiple_books',
      'unreadable',
    ]) &&
    isNullableEnum(value.region_type, [
      'book',
      'multiple_books',
      'non_book',
      'uncertain',
    ]) &&
    isNullableString(value.region_text) &&
    (value.suggested_match === null || isMatchCandidate(value.suggested_match)) &&
    validStatus &&
    validReasons &&
    validRead &&
    validMatch
  );
}

function isReviewItem(value: unknown): value is ReviewItem {
  if (!isAnalyzedBook(value) || !isRecord(value)) {
    return false;
  }
  const item = value as Record<string, unknown>;
  return (
    typeof item.id === 'string' &&
    Array.isArray(item.source_detection_indices) &&
    item.source_detection_indices.every((index) => typeof index === 'number') &&
    typeof item.duplicate_count === 'number' &&
    item.duplicate_count >= 1
  );
}

function hasReviewCounts(value: Record<string, unknown>): boolean {
  return (
    Array.isArray(value.source_detection_indices) &&
    value.source_detection_indices.every(
      (index) => typeof index === 'number',
    ) &&
    typeof value.item_count === 'number' &&
    Number.isInteger(value.item_count) &&
    value.item_count >= 1 &&
    typeof value.total_entries === 'number' &&
    Number.isInteger(value.total_entries) &&
    value.total_entries >= value.item_count &&
    typeof value.detection_count === 'number' &&
    Number.isInteger(value.detection_count) &&
    value.detection_count >= 1
  );
}

function isReviewVolumeBucket(value: unknown): value is ReviewVolumeBucket {
  if (!isRecord(value) || !Array.isArray(value.items)) {
    return false;
  }
  return (
    typeof value.id === 'string' &&
    typeof value.volume === 'string' &&
    value.volume.trim().length > 0 &&
    typeof value.representative_item_id === 'string' &&
    value.items.length > 0 &&
    value.items.every(isReviewItem) &&
    value.items.some((item) => item.id === value.representative_item_id) &&
    hasReviewCounts(value)
  );
}

function isReviewGroup(value: unknown): value is ReviewGroup {
  if (
    !isRecord(value) ||
    typeof value.id !== 'string' ||
    !isNullableString(value.title) ||
    !isNullableString(value.author) ||
    !['high_confidence', 'review_required', 'unmatched'].includes(
      String(value.review_status),
    ) ||
    typeof value.representative_item_id !== 'string' ||
    !hasReviewCounts(value)
  ) {
    return false;
  }

  if (value.group_type === 'ordinary') {
    return (
      Array.isArray(value.items) &&
      value.items.length > 0 &&
      value.items.every(isReviewItem) &&
      value.items.some((item) => item.id === value.representative_item_id)
    );
  }
  if (value.group_type === 'series') {
    if (
      !Array.isArray(value.volumes) ||
      !value.volumes.every(isReviewVolumeBucket) ||
      !Array.isArray(value.unknown_volume_items) ||
      !value.unknown_volume_items.every(isReviewItem)
    ) {
      return false;
    }
    const items = [
      ...value.volumes.flatMap((volume) => volume.items),
      ...value.unknown_volume_items,
    ];
    return (
      value.volumes.length > 0 &&
      items.some((item) => item.id === value.representative_item_id)
    );
  }
  return false;
}

function isCropThumbnail(value: unknown): value is CropThumbnail {
  return (
    isRecord(value) &&
    typeof value.detection_index === 'number' &&
    typeof value.data_url === 'string' &&
    value.data_url.startsWith('data:image/jpeg;base64,')
  );
}

function isAnalyzeResult(value: unknown): value is AnalyzeResult {
  if (typeof value !== 'object' || value === null) {
    return false;
  }

  const result = value as Record<string, unknown>;
  return (
    result.status === 'received' &&
    typeof result.filename === 'string' &&
    typeof result.width === 'number' &&
    typeof result.height === 'number' &&
    typeof result.detection_count === 'number' &&
    Array.isArray(result.books) &&
    result.books.every(isAnalyzedBook) &&
    Array.isArray(result.review_items) &&
    result.review_items.every(isReviewItem) &&
    Array.isArray(result.review_groups) &&
    result.review_groups.every(isReviewGroup) &&
    Array.isArray(result.crop_thumbnails) &&
    result.crop_thumbnails.every(isCropThumbnail) &&
    Array.isArray(result.warnings) &&
    result.warnings.every((warning) => typeof warning === 'string')
  );
}

function isLibraryBook(value: unknown): value is LibraryBook {
  return (
    isRecord(value) &&
    typeof value.id === 'number' &&
    isNullableString(value.catalog_id) &&
    typeof value.title === 'string' &&
    isNullableString(value.author) &&
    (value.source === 'catalog' || value.source === 'manual') &&
    typeof value.created_at === 'string'
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

function apiUrl(path: string): string {
  if (!API_BASE_URL) {
    throw new ShelfieApiError(
      'The API URL is not configured. Set EXPO_PUBLIC_API_BASE_URL and restart Expo.',
    );
  }
  return `${API_BASE_URL}${path}`;
}

async function requestJson(
  path: string,
  options: RequestInit,
  networkError: string,
): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), options);
  } catch (error) {
    if (error instanceof ShelfieApiError) {
      throw error;
    }
    throw new ShelfieApiError(networkError);
  }

  let responseBody: unknown;
  try {
    responseBody = await response.json();
  } catch {
    throw new ShelfieApiError('The backend returned an unreadable response.');
  }

  if (!response.ok) {
    throw new ShelfieApiError(
      responseError(responseBody) || `The request failed with HTTP ${response.status}.`,
    );
  }
  return responseBody;
}

export async function analyzeBookshelfPhoto(
  selectedImage: UploadablePhoto,
): Promise<AnalyzeResult> {
  const formData = new FormData();
  const imagePart = {
    uri: selectedImage.uri,
    name: filenameFor(selectedImage),
    type: selectedImage.mimeType || 'image/jpeg',
  };
  // React Native accepts file descriptors here; the shared DOM type only
  // describes browser Blob values.
  formData.append('image', imagePart as unknown as Blob);

  const responseBody = await requestJson(
    '/api/analyze/',
    {
      method: 'POST',
      body: formData,
    },
    'Shelfie could not reach the backend. Check that Django is running and both devices are on the same network.',
  );

  if (!isAnalyzeResult(responseBody)) {
    throw new ShelfieApiError('The backend returned an unexpected response.');
  }

  return responseBody;
}

export async function loadLibrary(): Promise<LibraryBook[]> {
  const responseBody = await requestJson(
    '/api/library/',
    { method: 'GET' },
    'Shelfie could not load the library. Check that Django is running.',
  );
  if (
    !isRecord(responseBody) ||
    !Array.isArray(responseBody.books) ||
    !responseBody.books.every(isLibraryBook)
  ) {
    throw new ShelfieApiError('The backend returned an unexpected library response.');
  }
  return responseBody.books;
}

export async function clearLibrary(): Promise<ClearLibraryResponse> {
  const responseBody = await requestJson(
    '/api/library/',
    { method: 'DELETE' },
    'Shelfie could not clear the library. Check that Django is running.',
  );
  if (
    !isRecord(responseBody) ||
    typeof responseBody.deleted !== 'number' ||
    !Number.isInteger(responseBody.deleted) ||
    responseBody.deleted < 0
  ) {
    throw new ShelfieApiError('The backend returned an unexpected clear response.');
  }
  return { deleted: responseBody.deleted };
}

async function saveBook(payload: object): Promise<LibraryBook> {
  const responseBody = await requestJson(
    '/api/library/',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    'Shelfie could not save this book. Check that Django is running.',
  );
  if (!isRecord(responseBody) || !isLibraryBook(responseBody.book)) {
    throw new ShelfieApiError('The backend returned an unexpected save response.');
  }
  return responseBody.book;
}

export function saveCatalogBook(catalogId: string): Promise<LibraryBook> {
  return saveBook({ catalog_id: catalogId });
}

export function saveManualBook(
  title: string,
  author: string,
): Promise<LibraryBook> {
  return saveBook({ title, author });
}
