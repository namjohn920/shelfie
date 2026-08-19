import { StyleSheet, Text, View } from 'react-native';

import type { UploadResult } from '../types/api';

type UploadResultCardProps = {
  result: UploadResult;
};

export function UploadResultCard({ result }: UploadResultCardProps) {
  return (
    <View style={styles.successCard}>
      <Text style={styles.successTitle}>✓ Analysis complete</Text>
      <Text style={styles.messageText}>Filename: {result.filename}</Text>
      <Text style={styles.messageText}>
        Size: {result.width} × {result.height}
      </Text>
      <Text style={styles.messageText}>
        Detected regions: {result.detection_count}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  successCard: {
    backgroundColor: '#e1f1e5',
    borderRadius: 10,
    marginTop: 20,
    padding: 16,
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
});
