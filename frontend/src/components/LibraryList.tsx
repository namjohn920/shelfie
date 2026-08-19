import {
  ActivityIndicator,
  Alert,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import type { LibraryBook } from '../types/api';

type LibraryListProps = {
  books: LibraryBook[];
  error: string | null;
  isClearing: boolean;
  isLoading: boolean;
  onClear: () => Promise<void>;
  onRetry: () => void;
};

export function LibraryList({
  books,
  error,
  isClearing,
  isLoading,
  onClear,
  onRetry,
}: LibraryListProps) {
  const confirmClear = () => {
    Alert.alert(
      'Clear your library?',
      'This will remove all saved books.\nThis cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear Library',
          style: 'destructive',
          onPress: () => void onClear(),
        },
      ],
    );
  };

  return (
    <View style={styles.section}>
      <View style={styles.headingRow}>
        <Text style={styles.heading}>My Library</Text>
        {books.length > 0 && !isLoading ? (
          <Pressable
            accessibilityRole="button"
            disabled={isClearing}
            onPress={confirmClear}
            style={({ pressed }) => [
              styles.clearButton,
              isClearing && styles.disabled,
              pressed && styles.pressed,
            ]}
          >
            {isClearing ? (
              <ActivityIndicator color="#8a3730" size="small" />
            ) : (
              <Text style={styles.clearButtonText}>Clear Library</Text>
            )}
          </Pressable>
        ) : null}
      </View>
      {isLoading ? <ActivityIndicator color="#315f42" style={styles.loading} /> : null}
      {!isLoading && books.length === 0 ? (
        <Text style={styles.emptyText}>No saved books yet.</Text>
      ) : null}
      {books.map((book) => (
        <View key={book.id} style={styles.bookRow}>
          <Text style={styles.bookTitle}>{book.title}</Text>
          {book.author ? <Text style={styles.bookAuthor}>{book.author}</Text> : null}
        </View>
      ))}
      {error ? (
        <View style={styles.errorCard}>
          <Text accessibilityRole="alert" style={styles.errorText}>
            {error}
          </Text>
          <Pressable accessibilityRole="button" onPress={onRetry} style={styles.retry}>
            <Text style={styles.retryText}>Retry library</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    borderTopColor: '#d8d4ca',
    borderTopWidth: 1,
    marginTop: 36,
    paddingTop: 28,
  },
  heading: {
    color: '#20251f',
    fontSize: 26,
    fontWeight: '700',
  },
  headingRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  clearButton: {
    borderColor: '#b97870',
    borderRadius: 8,
    borderWidth: 1,
    minHeight: 36,
    minWidth: 102,
    paddingHorizontal: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  clearButtonText: {
    color: '#8a3730',
    fontSize: 13,
    fontWeight: '600',
  },
  loading: {
    alignSelf: 'flex-start',
    marginTop: 16,
  },
  emptyText: {
    color: '#747a72',
    marginTop: 12,
  },
  bookRow: {
    backgroundColor: '#ffffff',
    borderRadius: 10,
    marginTop: 10,
    padding: 14,
  },
  bookTitle: {
    color: '#20251f',
    fontSize: 16,
    fontWeight: '700',
  },
  bookAuthor: {
    color: '#596056',
    marginTop: 3,
  },
  errorCard: {
    backgroundColor: '#f8dfdc',
    borderRadius: 10,
    marginTop: 12,
    padding: 14,
  },
  errorText: {
    color: '#7c2920',
    lineHeight: 20,
  },
  retry: {
    alignSelf: 'flex-start',
    marginTop: 8,
  },
  retryText: {
    color: '#7c2920',
    fontWeight: '700',
  },
  disabled: {
    opacity: 0.55,
  },
  pressed: {
    opacity: 0.78,
  },
});
