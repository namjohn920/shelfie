import type { ImagePickerAsset } from 'expo-image-picker';
import { StatusBar } from 'expo-status-bar';
import { useState } from 'react';
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
  ShelfieApiError,
} from '../api/shelfieApi';
import { BookshelfPhotoPicker } from '../components/BookshelfPhotoPicker';
import { UploadResultCard } from '../components/UploadResultCard';
import type { UploadResult } from '../types/api';

export function ScanScreen() {
  const [selectedPhoto, setSelectedPhoto] = useState<ImagePickerAsset | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const photoSelected = (photo: ImagePickerAsset) => {
    setSelectedPhoto(photo);
    setUploadResult(null);
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
      setUploadResult(await analyzeBookshelfPhoto(selectedPhoto));
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
          <Text style={styles.statusText}>Uploading image…</Text>
        ) : null}

        {uploadResult ? <UploadResultCard result={uploadResult} /> : null}

        {error ? (
          <View style={styles.errorCard}>
            <Text accessibilityRole="alert" style={styles.errorText}>
              {error}
            </Text>
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
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
