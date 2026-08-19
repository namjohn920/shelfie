import type { ImagePickerAsset } from 'expo-image-picker';
import { StatusBar } from 'expo-status-bar';
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import {
  analyzeBookshelfPhoto,
  clearLibrary,
  loadLibrary,
  saveCatalogBook,
  saveManualBook,
  ShelfieApiError,
} from '../api/shelfieApi';
import { AnalysisResults } from '../components/AnalysisResults';
import { BookshelfPhotoPicker } from '../components/BookshelfPhotoPicker';
import { LibraryList } from '../components/LibraryList';
import { UploadResultCard } from '../components/UploadResultCard';
import type {
  LibraryBook,
  ReviewGroup,
  ReviewItem,
  ReviewStatus,
  ReviewVolumeBucket,
  UploadResult,
} from '../types/api';

export function ScanScreen() {
  const [selectedPhoto, setSelectedPhoto] = useState<ImagePickerAsset | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingReviewGroups, setPendingReviewGroups] = useState<ReviewGroup[]>([]);
  const [libraryBooks, setLibraryBooks] = useState<LibraryBook[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);
  const [isLibraryClearing, setIsLibraryClearing] = useState(false);
  const [isLibraryLoading, setIsLibraryLoading] = useState(true);

  const refreshLibrary = useCallback(async () => {
    setLibraryError(null);
    setIsLibraryLoading(true);
    try {
      setLibraryBooks(await loadLibrary());
    } catch (loadError) {
      setLibraryError(
        loadError instanceof ShelfieApiError
          ? loadError.message
          : 'Shelfie could not load the library.',
      );
    } finally {
      setIsLibraryLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshLibrary();
  }, [refreshLibrary]);

  const photoSelected = (photo: ImagePickerAsset) => {
    setSelectedPhoto(photo);
    setUploadResult(null);
    setPendingReviewGroups([]);
  };

  const analyzePhoto = async () => {
    setError(null);
    setUploadResult(null);

    if (!selectedPhoto) {
      setError('Choose a bookshelf photo before analyzing.');
      return;
    }

    setIsLoading(true);

    try {
      const result = await analyzeBookshelfPhoto(selectedPhoto);
      setUploadResult(result);
      setPendingReviewGroups(result.review_groups);
    } catch (uploadError) {
      setError(
        uploadError instanceof ShelfieApiError
          ? uploadError.message
          : 'Shelfie could not analyze the photo. Please try again.',
      );
    } finally {
      setIsLoading(false);
    }
  };

  const saveCatalog = async (catalogId: string) => {
    await saveCatalogBook(catalogId);
    await refreshLibrary();
  };

  const saveManual = async (title: string, author: string) => {
    await saveManualBook(title, author);
    await refreshLibrary();
  };

  const clearSavedLibrary = async () => {
    if (isLibraryClearing) {
      return;
    }
    setLibraryError(null);
    setIsLibraryClearing(true);
    try {
      await clearLibrary();
      setLibraryBooks([]);
    } catch (clearError) {
      setLibraryError(
        clearError instanceof ShelfieApiError
          ? clearError.message
          : 'Shelfie could not clear the library.',
      );
    } finally {
      setIsLibraryClearing(false);
    }
  };

  const discardReviewItems = (itemIds: string[]) => {
    setPendingReviewGroups((groups) =>
      removeReviewItems(groups, new Set(itemIds)),
    );
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <ScrollView
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.title}>Shelfie</Text>
        <Text style={styles.subtitle}>Turn your bookshelf into a library.</Text>

        <BookshelfPhotoPicker
          disabled={isLoading}
          onError={setError}
          onPhotoSelected={photoSelected}
          selectedPhoto={selectedPhoto}
        />

        <Pressable
          accessibilityRole="button"
          disabled={isLoading}
          onPress={analyzePhoto}
          style={({ pressed }) => [
            styles.button,
            styles.primaryButton,
            isLoading && styles.buttonDisabled,
            pressed && styles.buttonPressed,
          ]}
        >
          {isLoading ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.primaryButtonText}>Analyze</Text>
          )}
        </Pressable>

        {isLoading ? (
          <Text style={styles.statusText}>Detecting and reading books…</Text>
        ) : null}

        {uploadResult ? <UploadResultCard result={uploadResult} /> : null}

        {uploadResult ? (
          <AnalysisResults
            cropThumbnails={uploadResult.crop_thumbnails}
            onDiscardItems={discardReviewItems}
            onSaveCatalog={saveCatalog}
            onSaveManual={saveManual}
            reviewGroups={pendingReviewGroups}
          />
        ) : null}

        {error ? (
          <View style={styles.errorCard}>
            <Text accessibilityRole="alert" style={styles.errorText}>
              {error}
            </Text>
          </View>
        ) : null}

        <LibraryList
          books={libraryBooks}
          error={libraryError}
          isClearing={isLibraryClearing}
          isLoading={isLibraryLoading}
          onClear={clearSavedLibrary}
          onRetry={() => void refreshLibrary()}
        />
      </ScrollView>
    </SafeAreaView>
  );
}

function removeReviewItems(
  groups: ReviewGroup[],
  discardedIds: Set<string>,
): ReviewGroup[] {
  return groups.flatMap<ReviewGroup>((group): ReviewGroup[] => {
    if (group.group_type === 'ordinary') {
      const items = group.items.filter((item) => !discardedIds.has(item.id));
      if (items.length === 0) {
        return [];
      }
      return [
        {
          ...group,
          ...reviewCounts(items),
          items,
          representative_item_id: remainingRepresentative(
            items,
            group.representative_item_id,
          ),
          review_status: groupedStatus(items),
        },
      ];
    }

    const volumes = group.volumes.flatMap<ReviewVolumeBucket>(
      (volume): ReviewVolumeBucket[] => {
        const items = volume.items.filter(
          (item) => !discardedIds.has(item.id),
        );
        if (items.length === 0) {
          return [];
        }
        return [
          {
            ...volume,
            ...reviewCounts(items),
            items,
            representative_item_id: remainingRepresentative(
              items,
              volume.representative_item_id,
            ),
          } satisfies ReviewVolumeBucket,
        ];
      },
    );
    const unknownVolumeItems = group.unknown_volume_items.filter(
      (item) => !discardedIds.has(item.id),
    );
    const allItems = [
      ...volumes.flatMap((volume) => volume.items),
      ...unknownVolumeItems,
    ];
    if (allItems.length === 0) {
      return [];
    }
    return [
      {
        ...group,
        ...reviewCounts(allItems),
        volumes,
        unknown_volume_items: unknownVolumeItems,
        representative_item_id: remainingRepresentative(
          allItems,
          group.representative_item_id,
        ),
        review_status: groupedStatus(allItems),
      },
    ];
  });
}

function reviewCounts(items: ReviewItem[]) {
  const sourceDetectionIndices = [
    ...new Set(items.flatMap((item) => item.source_detection_indices)),
  ].sort((first, second) => first - second);
  return {
    source_detection_indices: sourceDetectionIndices,
    item_count: items.length,
    total_entries: items.reduce(
      (total, item) => total + item.duplicate_count,
      0,
    ),
    detection_count: sourceDetectionIndices.length,
  };
}

function remainingRepresentative(
  items: ReviewItem[],
  currentRepresentativeId: string,
): string {
  return items.some((item) => item.id === currentRepresentativeId)
    ? currentRepresentativeId
    : items[0].id;
}

function groupedStatus(items: ReviewItem[]): ReviewStatus {
  const statuses = new Set(items.map((item) => item.review.status));
  if (statuses.size === 1 && statuses.has('high_confidence')) {
    return 'high_confidence';
  }
  if (statuses.size === 1 && statuses.has('unmatched')) {
    return 'unmatched';
  }
  return 'review_required';
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#f5f1e8',
  },
  container: {
    flexGrow: 1,
    paddingHorizontal: 24,
    paddingVertical: 40,
  },
  title: {
    color: '#20251f',
    fontSize: 40,
    fontWeight: '700',
  },
  subtitle: {
    color: '#596056',
    fontSize: 18,
    marginBottom: 32,
    marginTop: 6,
  },
  button: {
    alignItems: 'center',
    borderRadius: 10,
    minHeight: 50,
    justifyContent: 'center',
    paddingHorizontal: 18,
  },
  buttonPressed: {
    opacity: 0.78,
  },
  buttonDisabled: {
    opacity: 0.6,
  },
  primaryButton: {
    backgroundColor: '#315f42',
  },
  primaryButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '700',
  },
  statusText: {
    color: '#596056',
    marginTop: 14,
    textAlign: 'center',
  },
  errorCard: {
    backgroundColor: '#f8dfdc',
    borderRadius: 10,
    marginTop: 20,
    padding: 16,
  },
  errorText: {
    color: '#7c2920',
    lineHeight: 20,
  },
});
