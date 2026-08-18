import { StatusBar } from 'expo-status-bar';
import * as ImagePicker from 'expo-image-picker';
import { useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/+$/, '');

type UploadResult = {
  status: 'received';
  filename: string;
  width: number;
  height: number;
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

function filenameFor(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.fileName) {
    return asset.fileName;
  }

  const uriFilename = asset.uri.split('/').pop()?.split('?')[0];
  return uriFilename || 'bookshelf.jpg';
}

export default function App() {
  const [selectedImage, setSelectedImage] =
    useState<ImagePicker.ImagePickerAsset | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const choosePhoto = async () => {
    setError(null);

    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        setError('Photo library permission is required to choose a bookshelf photo.');
        return;
      }

      const pickerResult = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ['images'],
        allowsEditing: false,
        quality: 1,
        preferredAssetRepresentationMode:
          ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
      });

      if (!pickerResult.canceled) {
        setSelectedImage(pickerResult.assets[0]);
        setUploadResult(null);
      }
    } catch {
      setError('Shelfie could not open the photo library. Please try again.');
    }
  };

  const analyzePhoto = async () => {
    setError(null);
    setUploadResult(null);

    if (!selectedImage) {
      setError('Choose a bookshelf photo before analyzing.');
      return;
    }

    if (!API_BASE_URL) {
      setError(
        'The API URL is not configured. Set EXPO_PUBLIC_API_BASE_URL and restart Expo.',
      );
      return;
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

    setIsLoading(true);

    try {
      let response: Response;
      try {
        response = await fetch(`${API_BASE_URL}/api/analyze/`, {
          method: 'POST',
          body: formData,
        });
      } catch {
        setError(
          'Shelfie could not reach the backend. Check that Django is running and both devices are on the same network.',
        );
        return;
      }

      let responseBody: unknown;
      try {
        responseBody = await response.json();
      } catch {
        setError('The backend returned an unreadable response.');
        return;
      }

      if (!response.ok) {
        setError(
          responseError(responseBody) ||
            `The upload failed with HTTP ${response.status}.`,
        );
        return;
      }

      if (!isUploadResult(responseBody)) {
        setError('The backend returned an unexpected response.');
        return;
      }

      setUploadResult(responseBody);
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

        <Pressable
          accessibilityRole="button"
          disabled={isLoading}
          onPress={choosePhoto}
          style={({ pressed }) => [
            styles.button,
            styles.secondaryButton,
            pressed && styles.buttonPressed,
          ]}
        >
          <Text style={styles.secondaryButtonText}>Choose Bookshelf Photo</Text>
        </Pressable>

        {selectedImage ? (
          <View style={styles.previewCard}>
            <Image
              accessibilityLabel="Selected bookshelf"
              source={{ uri: selectedImage.uri }}
              style={styles.preview}
            />
            <Text numberOfLines={1} style={styles.filename}>
              {filenameFor(selectedImage)}
            </Text>
          </View>
        ) : (
          <Text style={styles.emptyText}>No photo selected.</Text>
        )}

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

        {uploadResult ? (
          <View style={[styles.messageCard, styles.successCard]}>
            <Text style={styles.successTitle}>✓ Image received by Shelfie</Text>
            <Text style={styles.messageText}>
              Filename: {uploadResult.filename}
            </Text>
            <Text style={styles.messageText}>
              Size: {uploadResult.width} × {uploadResult.height}
            </Text>
          </View>
        ) : null}

        {error ? (
          <View style={[styles.messageCard, styles.errorCard]}>
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
  secondaryButton: {
    backgroundColor: '#ffffff',
    borderColor: '#315f42',
    borderWidth: 1,
  },
  secondaryButtonText: {
    color: '#315f42',
    fontSize: 16,
    fontWeight: '600',
  },
  previewCard: {
    backgroundColor: '#ffffff',
    borderRadius: 12,
    marginVertical: 20,
    overflow: 'hidden',
  },
  preview: {
    aspectRatio: 4 / 3,
    backgroundColor: '#dedbd2',
    width: '100%',
  },
  filename: {
    color: '#596056',
    padding: 12,
  },
  emptyText: {
    color: '#747a72',
    marginVertical: 30,
    textAlign: 'center',
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
  messageCard: {
    borderRadius: 10,
    marginTop: 20,
    padding: 16,
  },
  successCard: {
    backgroundColor: '#e1f1e5',
  },
  successTitle: {
    color: '#234c31',
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 8,
  },
  messageText: {
    color: '#2f4736',
    marginTop: 3,
  },
  errorCard: {
    backgroundColor: '#f8dfdc',
  },
  errorText: {
    color: '#7c2920',
    lineHeight: 20,
  },
});
