import * as ImagePicker from 'expo-image-picker';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

type BookshelfPhotoPickerProps = {
  disabled: boolean;
  selectedPhoto: ImagePicker.ImagePickerAsset | null;
  onError: (message: string | null) => void;
  onPhotoSelected: (photo: ImagePicker.ImagePickerAsset) => void;
};

function filenameFor(asset: ImagePicker.ImagePickerAsset): string {
  if (asset.fileName) {
    return asset.fileName;
  }

  const uriFilename = asset.uri.split('/').pop()?.split('?')[0];
  return uriFilename || 'bookshelf.jpg';
}

export function BookshelfPhotoPicker({
  disabled,
  selectedPhoto,
  onError,
  onPhotoSelected,
}: BookshelfPhotoPickerProps) {
  const choosePhoto = async () => {
    onError(null);

    try {
      const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
      if (!permission.granted) {
        onError('Photo library permission is required to choose a bookshelf photo.');
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
        onPhotoSelected(pickerResult.assets[0]);
      }
    } catch {
      onError('Shelfie could not open the photo library. Please try again.');
    }
  };

  return (
    <>
      <Pressable
        accessibilityRole="button"
        disabled={disabled}
        onPress={choosePhoto}
        style={({ pressed }) => [
          styles.button,
          styles.secondaryButton,
          pressed && styles.buttonPressed,
        ]}
      >
        <Text style={styles.secondaryButtonText}>Choose Bookshelf Photo</Text>
      </Pressable>

      {selectedPhoto ? (
        <View style={styles.previewCard}>
          <Image
            accessibilityLabel="Selected bookshelf"
            source={{ uri: selectedPhoto.uri }}
            style={styles.preview}
          />
          <Text numberOfLines={1} style={styles.filename}>
            {filenameFor(selectedPhoto)}
          </Text>
        </View>
      ) : (
        <Text style={styles.emptyText}>No photo selected.</Text>
      )}
    </>
  );
}

const styles = StyleSheet.create({
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
});
