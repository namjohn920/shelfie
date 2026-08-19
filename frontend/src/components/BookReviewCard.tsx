import { useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ShelfieApiError } from '../api/shelfieApi';
import type { CropThumbnail, ReviewItem, ReviewReason } from '../types/api';

type BookReviewCardProps = {
  book: ReviewItem;
  sourceThumbnails?: CropThumbnail[];
  groupedItems?: ReviewItem[];
  groupedDetectionCount?: number;
  groupedEntryCount?: number;
  discardLabel?: string;
  presentationTitle?: string | null;
  presentationAuthor?: string | null;
  onDiscard: () => void;
  onSaveCatalog: (catalogId: string) => Promise<void>;
  onSaveManual: (title: string, author: string) => Promise<void>;
};

const REASON_MESSAGES: Record<ReviewReason, string> = {
  read_failed: 'The AI reader failed for this detected region.',
  unreadable: 'The AI could not read usable book text.',
  no_evidence: 'No usable title or author was recovered.',
  no_candidate: 'No close catalog candidate was found.',
  partial_read: 'Only part of the book text was readable.',
  low_score: 'Match score is below the high-confidence threshold.',
  small_margin: 'The best match is too close to another candidate.',
  candidate_not_reliable_enough_to_show:
    'The raw catalog candidate was not reliable enough to show as a suggestion.',
  non_book: 'The detected region looks like a non-book object.',
  high_confidence: 'Strong readable catalog match.',
};

function statusLabel(book: ReviewItem): string {
  if (book.region_type === 'non_book') {
    return 'Likely not a book';
  }
  if (book.review.status === 'high_confidence') {
    return 'Ready to add';
  }
  if (book.review.status === 'review_required') {
    return 'Needs review';
  }
  return 'Unmatched / unreadable';
}

function readLabel(book: ReviewItem): string {
  const title = book.read?.title
    ? `${book.read.title}${book.read.volume ? ` · Volume ${book.read.volume}` : ''}`
    : null;
  return title || book.read?.author
    ? [title, book.read?.author].filter(Boolean).join(' — ')
    : 'No title or author recovered';
}

export function BookReviewCard({
  book,
  sourceThumbnails = [],
  groupedItems = [],
  groupedDetectionCount = 1,
  groupedEntryCount = 1,
  discardLabel = 'Discard',
  presentationTitle = null,
  presentationAuthor = null,
  onDiscard,
  onSaveCatalog,
  onSaveManual,
}: BookReviewCardProps) {
  const suggested = book.suggested_match?.catalog ?? null;
  const isNonBook = book.region_type === 'non_book';
  const [title, setTitle] = useState(book.read?.title ?? '');
  const [author, setAuthor] = useState(book.read?.author ?? '');
  const [manualVisible, setManualVisible] = useState(!suggested && !isNonBook);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved'>('idle');
  const [savingAction, setSavingAction] = useState<'catalog' | 'manual' | null>(
    null,
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showGroupedSources, setShowGroupedSources] = useState(false);
  const saveLocked = useRef(false);
  const hasGroupedSources =
    sourceThumbnails.length > 1 || groupedItems.length > 1;
  const visibleThumbnails = showGroupedSources
    ? sourceThumbnails
    : sourceThumbnails.slice(0, 1);

  const runSave = async (
    action: 'catalog' | 'manual',
    save: () => Promise<void>,
  ) => {
    if (saveState !== 'idle' || saveLocked.current) {
      return;
    }
    saveLocked.current = true;
    setSaveError(null);
    setSaveState('saving');
    setSavingAction(action);
    try {
      await save();
      setSaveState('saved');
      setSavingAction(null);
    } catch (error) {
      saveLocked.current = false;
      setSaveState('idle');
      setSavingAction(null);
      setSaveError(
        error instanceof ShelfieApiError
          ? error.message
          : 'Shelfie could not save this book. Please try again.',
      );
    }
  };

  const saveManual = () => {
    if (!title.trim()) {
      setSaveError('Enter a title before adding this book.');
      return;
    }
    void runSave('manual', () => onSaveManual(title, author));
  };

  const isDisabled = saveState !== 'idle';
  const visibleText = book.region_text || book.read?.raw_text;

  return (
    <View style={styles.card}>
      <View style={showGroupedSources ? styles.thumbnailGrid : undefined}>
        {visibleThumbnails.map((thumbnail) => (
          <Image
            accessibilityLabel={`Detected source region ${thumbnail.detection_index}`}
            key={thumbnail.detection_index}
            resizeMode="contain"
            source={{ uri: thumbnail.data_url }}
            style={[
              styles.thumbnail,
              showGroupedSources && sourceThumbnails.length > 1
                ? styles.groupedThumbnail
                : undefined,
            ]}
          />
        ))}
      </View>

      <Text style={styles.status}>{statusLabel(book)}</Text>
      {presentationTitle ? (
        <>
          <Text style={styles.presentationTitle}>{presentationTitle}</Text>
          {presentationAuthor ? (
            <Text style={styles.presentationAuthor}>{presentationAuthor}</Text>
          ) : null}
        </>
      ) : null}
      {groupedDetectionCount > 1 ? (
        <Text style={styles.groupedCount}>
          {groupedDetectionCount} detections grouped
        </Text>
      ) : groupedEntryCount > 1 ? (
        <Text style={styles.groupedCount}>
          {groupedEntryCount} review results grouped
        </Text>
      ) : book.duplicate_count > 1 ? (
        <Text style={styles.traceText}>
          Combined {book.duplicate_count} overlapping reads · detections{' '}
          {book.source_detection_indices.join(', ')}
        </Text>
      ) : null}

      {hasGroupedSources ? (
        <ActionButton
          disabled={false}
          label={showGroupedSources ? 'Hide grouped sources' : 'Show grouped sources'}
          onPress={() => setShowGroupedSources((current) => !current)}
        />
      ) : null}

      {showGroupedSources && groupedItems.length > 1 ? (
        <View style={styles.groupedEntries}>
          <Text style={styles.groupedEntriesHeading}>Grouped review entries</Text>
          {groupedItems.map((item) => (
            <Text key={item.id} style={styles.groupedEntryText}>
              {readLabel(item)} · detections{' '}
              {item.source_detection_indices.join(', ')}
            </Text>
          ))}
        </View>
      ) : null}

      {isNonBook ? (
        visibleText ? (
          <Text style={styles.evidence}>Visible text: {visibleText}</Text>
        ) : (
          <Text style={styles.evidence}>No reliable book details were found.</Text>
        )
      ) : (
        <Text style={styles.evidence}>AI read: {readLabel(book)}</Text>
      )}

      {!isNonBook && suggested ? (
        <View style={styles.suggestion}>
          <Text style={styles.suggestionLabel}>
            {book.review.status === 'high_confidence'
              ? 'Catalog match'
              : 'Possible catalog match'}
          </Text>
          <Text style={styles.bookTitle}>{suggested.title}</Text>
          <Text style={styles.bookAuthor}>{suggested.author}</Text>
          {book.match?.combined_score !== null ? (
            <Text style={styles.score}>
              Score {book.match?.combined_score?.toFixed(1)} · margin{' '}
              {book.match?.margin?.toFixed(1) ?? 'unknown'}
            </Text>
          ) : null}
        </View>
      ) : null}

      {!isNonBook && !suggested ? (
        <Text style={styles.noSuggestion}>No reliable catalog match found.</Text>
      ) : null}

      {book.review.status !== 'high_confidence' && !isNonBook ? (
        <Text style={styles.reason}>
          {book.review.reasons.map((reason) => REASON_MESSAGES[reason]).join(' ')}
        </Text>
      ) : null}

      {saveState === 'saved' ? (
        <Text accessibilityRole="alert" style={styles.savedText}>
          ✓ Saved to My Library
        </Text>
      ) : (
        <>
          {manualVisible ? (
            <ManualBookForm
              author={author}
              disabled={isDisabled}
              onAuthorChange={setAuthor}
              onSave={saveManual}
              onTitleChange={setTitle}
              saving={savingAction === 'manual'}
              title={title}
            />
          ) : null}

          {!manualVisible && isNonBook ? (
            <ActionButton
              disabled={isDisabled}
              label="This is a book / Add manually"
              onPress={() => setManualVisible(true)}
            />
          ) : null}

          {!manualVisible && suggested ? (
            <>
              <ActionButton
                disabled={isDisabled}
                label={
                  book.review.status === 'high_confidence'
                    ? 'Add to Library'
                    : 'Add suggested book'
                }
                loading={savingAction === 'catalog'}
                onPress={() =>
                  void runSave('catalog', () =>
                    onSaveCatalog(suggested.catalog_id),
                  )
                }
                primary
              />
              <ActionButton
                disabled={isDisabled}
                label="Enter a different book"
                onPress={() => setManualVisible(true)}
              />
            </>
          ) : null}

          <ActionButton
            disabled={isDisabled}
            label={discardLabel}
            onPress={onDiscard}
          />
        </>
      )}

      {saveError ? (
        <Text accessibilityRole="alert" style={styles.errorText}>
          {saveError}
        </Text>
      ) : null}
    </View>
  );
}

type ManualBookFormProps = {
  author: string;
  disabled: boolean;
  onAuthorChange: (value: string) => void;
  onSave: () => void;
  onTitleChange: (value: string) => void;
  saving: boolean;
  title: string;
};

function ManualBookForm({
  author,
  disabled,
  onAuthorChange,
  onSave,
  onTitleChange,
  saving,
  title,
}: ManualBookFormProps) {
  return (
    <>
      <TextInput
        editable={!disabled}
        onChangeText={onTitleChange}
        placeholder="Book title"
        style={styles.input}
        value={title}
      />
      <TextInput
        editable={!disabled}
        onChangeText={onAuthorChange}
        placeholder="Author (optional)"
        style={styles.input}
        value={author}
      />
      <ActionButton
        disabled={disabled}
        label="Add as entered"
        loading={saving}
        onPress={onSave}
        primary
      />
    </>
  );
}

type ActionButtonProps = {
  disabled: boolean;
  label: string;
  loading?: boolean;
  onPress: () => void;
  primary?: boolean;
};

function ActionButton({
  disabled,
  label,
  loading = false,
  onPress,
  primary = false,
}: ActionButtonProps) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        primary ? styles.primaryButton : styles.secondaryButton,
        disabled && styles.disabled,
        pressed && styles.pressed,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={primary ? '#ffffff' : '#315f42'} />
      ) : (
        <Text style={primary ? styles.primaryButtonText : styles.secondaryButtonText}>
          {label}
        </Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#ffffff',
    borderColor: '#dedbd2',
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 12,
    padding: 16,
  },
  thumbnail: {
    backgroundColor: '#eeece6',
    borderRadius: 8,
    height: 150,
    marginBottom: 14,
    width: '100%',
  },
  thumbnailGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  groupedThumbnail: {
    height: 112,
    width: '48%',
  },
  status: {
    color: '#315f42',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 8,
  },
  traceText: {
    color: '#6a7169',
    fontSize: 12,
    marginBottom: 8,
  },
  groupedCount: {
    color: '#343a34',
    fontWeight: '700',
    marginBottom: 8,
    marginTop: 7,
  },
  presentationTitle: {
    color: '#20251f',
    fontSize: 19,
    fontWeight: '700',
  },
  presentationAuthor: {
    color: '#4e554e',
    marginTop: 3,
  },
  groupedEntries: {
    backgroundColor: '#f5f3ed',
    borderRadius: 8,
    marginBottom: 10,
    marginTop: 10,
    padding: 10,
  },
  groupedEntriesHeading: {
    color: '#4e554e',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 5,
    textTransform: 'uppercase',
  },
  groupedEntryText: {
    color: '#596056',
    fontSize: 12,
    lineHeight: 18,
  },
  evidence: {
    color: '#343a34',
    lineHeight: 20,
  },
  suggestion: {
    backgroundColor: '#eef3ee',
    borderRadius: 8,
    marginTop: 12,
    padding: 12,
  },
  suggestionLabel: {
    color: '#596056',
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  bookTitle: {
    color: '#20251f',
    fontSize: 16,
    fontWeight: '700',
    marginTop: 5,
  },
  bookAuthor: {
    color: '#4e554e',
    marginTop: 2,
  },
  score: {
    color: '#6a7169',
    fontSize: 12,
    marginTop: 7,
  },
  noSuggestion: {
    color: '#343a34',
    fontWeight: '600',
    marginTop: 12,
  },
  reason: {
    color: '#7a531d',
    lineHeight: 19,
    marginTop: 12,
  },
  input: {
    backgroundColor: '#ffffff',
    borderColor: '#aeb5ac',
    borderRadius: 8,
    borderWidth: 1,
    color: '#20251f',
    marginTop: 12,
    minHeight: 46,
    paddingHorizontal: 12,
  },
  button: {
    alignItems: 'center',
    borderRadius: 8,
    justifyContent: 'center',
    marginTop: 10,
    minHeight: 46,
    paddingHorizontal: 14,
  },
  primaryButton: {
    backgroundColor: '#315f42',
  },
  secondaryButton: {
    backgroundColor: '#ffffff',
    borderColor: '#315f42',
    borderWidth: 1,
  },
  primaryButtonText: {
    color: '#ffffff',
    fontWeight: '700',
  },
  secondaryButtonText: {
    color: '#315f42',
    fontWeight: '600',
  },
  disabled: {
    opacity: 0.55,
  },
  pressed: {
    opacity: 0.78,
  },
  savedText: {
    color: '#234c31',
    fontWeight: '700',
    marginTop: 14,
  },
  errorText: {
    color: '#7c2920',
    lineHeight: 20,
    marginTop: 10,
  },
});
