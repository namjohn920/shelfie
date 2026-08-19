import { useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View } from 'react-native';

import type {
  CropThumbnail,
  ReviewGroup,
  ReviewItem,
  ReviewStatus,
  ReviewVolumeBucket,
  SeriesReviewGroup,
} from '../types/api';
import { BookReviewCard } from './BookReviewCard';

const COLLAPSED_UNMATCHED_THRESHOLD = 5;

type AnalysisResultsProps = {
  reviewGroups: ReviewGroup[];
  cropThumbnails: CropThumbnail[];
  onDiscardItems: (itemIds: string[]) => void;
  onSaveCatalog: (catalogId: string) => Promise<void>;
  onSaveManual: (title: string, author: string) => Promise<void>;
};

export function AnalysisResults({
  reviewGroups,
  cropThumbnails,
  onDiscardItems,
  onSaveCatalog,
  onSaveManual,
}: AnalysisResultsProps) {
  const [showUnmatched, setShowUnmatched] = useState(false);
  const thumbnailByDetection = useMemo(
    () =>
      new Map(
        cropThumbnails.map((thumbnail) => [
          thumbnail.detection_index,
          thumbnail.data_url,
        ]),
      ),
    [cropThumbnails],
  );
  const readyToAdd = reviewGroups.filter(
    (group) => group.review_status === 'high_confidence',
  );
  const needsReview = reviewGroups.filter(
    (group) => group.review_status === 'review_required',
  );
  const unmatched = reviewGroups.filter(
    (group) => group.review_status === 'unmatched',
  );
  const unmatchedExpanded =
    unmatched.length <= COLLAPSED_UNMATCHED_THRESHOLD || showUnmatched;

  return (
    <View style={styles.section}>
      <Text style={styles.heading}>Results</Text>
      {reviewGroups.length === 0 ? (
        <Text style={styles.emptyText}>No book results were found in this image.</Text>
      ) : null}

      {readyToAdd.length > 0 ? (
        <ReviewGroupSection
          groups={readyToAdd}
          label={`Ready to add (${readyToAdd.length} groups)`}
          onDiscardItems={onDiscardItems}
          onSaveCatalog={onSaveCatalog}
          onSaveManual={onSaveManual}
          thumbnailByDetection={thumbnailByDetection}
        />
      ) : null}
      {needsReview.length > 0 ? (
        <ReviewGroupSection
          groups={needsReview}
          label={`Needs review (${needsReview.length} groups)`}
          onDiscardItems={onDiscardItems}
          onSaveCatalog={onSaveCatalog}
          onSaveManual={onSaveManual}
          thumbnailByDetection={thumbnailByDetection}
        />
      ) : null}
      {unmatched.length > 0 ? (
        <View style={styles.group}>
          <Text style={styles.groupHeading}>
            Unmatched / unreadable ({unmatched.length} groups)
          </Text>
          {unmatchedExpanded ? (
            <>
              {unmatched.map((group) => (
                <ReviewGroupCard
                  group={group}
                  key={group.id}
                  onDiscardItems={onDiscardItems}
                  onSaveCatalog={onSaveCatalog}
                  onSaveManual={onSaveManual}
                  thumbnailByDetection={thumbnailByDetection}
                />
              ))}
              {unmatched.length > COLLAPSED_UNMATCHED_THRESHOLD ? (
                <ToggleButton
                  label="Hide unmatched groups"
                  onPress={() => setShowUnmatched(false)}
                />
              ) : null}
            </>
          ) : (
            <ToggleButton
              label="Review unmatched groups"
              onPress={() => setShowUnmatched(true)}
            />
          )}
        </View>
      ) : null}
    </View>
  );
}

type ReviewGroupSectionProps = {
  groups: ReviewGroup[];
  label: string;
  onDiscardItems: (itemIds: string[]) => void;
  onSaveCatalog: (catalogId: string) => Promise<void>;
  onSaveManual: (title: string, author: string) => Promise<void>;
  thumbnailByDetection: Map<number, string>;
};

function ReviewGroupSection({
  groups,
  label,
  onDiscardItems,
  onSaveCatalog,
  onSaveManual,
  thumbnailByDetection,
}: ReviewGroupSectionProps) {
  return (
    <View style={styles.group}>
      <Text style={styles.groupHeading}>{label}</Text>
      {groups.map((group) => (
        <ReviewGroupCard
          group={group}
          key={group.id}
          onDiscardItems={onDiscardItems}
          onSaveCatalog={onSaveCatalog}
          onSaveManual={onSaveManual}
          thumbnailByDetection={thumbnailByDetection}
        />
      ))}
    </View>
  );
}

type ReviewGroupCardProps = {
  group: ReviewGroup;
  onDiscardItems: (itemIds: string[]) => void;
  onSaveCatalog: (catalogId: string) => Promise<void>;
  onSaveManual: (title: string, author: string) => Promise<void>;
  thumbnailByDetection: Map<number, string>;
};

function ReviewGroupCard(props: ReviewGroupCardProps) {
  if (props.group.group_type === 'series') {
    return <SeriesGroupCard {...props} group={props.group} />;
  }
  const group = props.group;

  const representative = representativeFrom(
    group.items,
    group.representative_item_id,
  );
  return (
    <BookReviewCard
      book={representative}
      discardLabel={
        group.item_count > 1 ? 'Discard group entries' : 'Discard'
      }
      groupedDetectionCount={group.detection_count}
      groupedEntryCount={group.total_entries}
      groupedItems={group.items}
      onDiscard={() =>
        props.onDiscardItems(group.items.map((item) => item.id))
      }
      onSaveCatalog={props.onSaveCatalog}
      onSaveManual={props.onSaveManual}
      presentationAuthor={group.author}
      presentationTitle={group.title}
      sourceThumbnails={thumbnailsFor(
        group.source_detection_indices,
        props.thumbnailByDetection,
      )}
    />
  );
}

type SeriesGroupCardProps = Omit<ReviewGroupCardProps, 'group'> & {
  group: SeriesReviewGroup;
};

function SeriesGroupCard({
  group,
  onDiscardItems,
  onSaveCatalog,
  onSaveManual,
  thumbnailByDetection,
}: SeriesGroupCardProps) {
  const [expanded, setExpanded] = useState(false);
  const allItems = [
    ...group.volumes.flatMap((volume) => volume.items),
    ...group.unknown_volume_items,
  ];
  const representative = representativeFrom(
    allItems,
    group.representative_item_id,
  );
  const thumbnail = thumbnailByDetection.get(representative.detection_index);
  const volumeLabel = `${group.volumes.length} identified ${plural(
    group.volumes.length,
    'volume',
  )} · ${group.detection_count} ${plural(
    group.detection_count,
    'detection',
  )}`;

  return (
    <View style={styles.seriesCard}>
      {thumbnail ? (
        <Image
          accessibilityLabel="Representative detected source region"
          resizeMode="contain"
          source={{ uri: thumbnail }}
          style={styles.seriesThumbnail}
        />
      ) : null}
      <Text style={styles.status}>{statusLabel(group.review_status)}</Text>
      <Text style={styles.seriesTitle}>{group.title || 'Unknown title'}</Text>
      {group.author ? <Text style={styles.seriesAuthor}>{group.author}</Text> : null}
      <Text style={styles.seriesCount}>{volumeLabel}</Text>
      {group.unknown_volume_items.length > 0 ? (
        <Text style={styles.unknownCount}>
          {group.unknown_volume_items.length}{' '}
          {plural(group.unknown_volume_items.length, 'item')} with unknown volume
        </Text>
      ) : null}
      <ToggleButton
        label={expanded ? 'Hide volumes' : 'Show volumes'}
        onPress={() => setExpanded((current) => !current)}
      />

      {expanded ? (
        <View style={styles.volumeList}>
          {group.volumes.map((volume) => (
            <VolumeReviewArea
              key={volume.id}
              onDiscardItems={onDiscardItems}
              onSaveCatalog={onSaveCatalog}
              onSaveManual={onSaveManual}
              thumbnailByDetection={thumbnailByDetection}
              volume={volume}
            />
          ))}
          {group.unknown_volume_items.length > 0 ? (
            <View style={styles.unknownSection}>
              <Text style={styles.volumeHeading}>Unknown volume</Text>
              <Text style={styles.volumeCount}>
                Kept as {group.unknown_volume_items.length} individual{' '}
                {plural(group.unknown_volume_items.length, 'item')}
              </Text>
              {group.unknown_volume_items.map((item) => (
                <BookReviewCard
                  book={item}
                  key={item.id}
                  onDiscard={() => onDiscardItems([item.id])}
                  onSaveCatalog={onSaveCatalog}
                  onSaveManual={onSaveManual}
                  sourceThumbnails={thumbnailsFor(
                    item.source_detection_indices,
                    thumbnailByDetection,
                  )}
                />
              ))}
            </View>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}

type VolumeReviewAreaProps = {
  volume: ReviewVolumeBucket;
  onDiscardItems: (itemIds: string[]) => void;
  onSaveCatalog: (catalogId: string) => Promise<void>;
  onSaveManual: (title: string, author: string) => Promise<void>;
  thumbnailByDetection: Map<number, string>;
};

function VolumeReviewArea({
  volume,
  onDiscardItems,
  onSaveCatalog,
  onSaveManual,
  thumbnailByDetection,
}: VolumeReviewAreaProps) {
  const representative = representativeFrom(
    volume.items,
    volume.representative_item_id,
  );
  return (
    <View style={styles.volumeArea}>
      <Text style={styles.volumeHeading}>Volume {volume.volume}</Text>
      <Text style={styles.volumeCount}>
        {volume.detection_count} {plural(volume.detection_count, 'detection')}
      </Text>
      <BookReviewCard
        book={representative}
        discardLabel={volume.item_count > 1 ? 'Discard group entries' : 'Discard'}
        groupedDetectionCount={volume.detection_count}
        groupedEntryCount={volume.total_entries}
        groupedItems={volume.items}
        onDiscard={() => onDiscardItems(volume.items.map((item) => item.id))}
        onSaveCatalog={onSaveCatalog}
        onSaveManual={onSaveManual}
        sourceThumbnails={thumbnailsFor(
          volume.source_detection_indices,
          thumbnailByDetection,
        )}
      />
    </View>
  );
}

function representativeFrom(
  items: ReviewItem[],
  representativeItemId: string,
): ReviewItem {
  const representative = items.find((item) => item.id === representativeItemId);
  return representative ?? items[0];
}

function thumbnailsFor(
  detectionIndices: number[],
  thumbnailByDetection: Map<number, string>,
): CropThumbnail[] {
  return detectionIndices.flatMap((detectionIndex) => {
    const dataUrl = thumbnailByDetection.get(detectionIndex);
    return dataUrl
      ? [{ detection_index: detectionIndex, data_url: dataUrl }]
      : [];
  });
}

function statusLabel(status: ReviewStatus): string {
  if (status === 'high_confidence') {
    return 'Ready to add';
  }
  if (status === 'review_required') {
    return 'Needs review';
  }
  return 'Unmatched / unreadable';
}

function plural(count: number, noun: string): string {
  return count === 1 ? noun : `${noun}s`;
}

function ToggleButton({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [styles.toggleButton, pressed && styles.pressed]}
    >
      <Text style={styles.toggleText}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  section: {
    marginTop: 28,
  },
  heading: {
    color: '#20251f',
    fontSize: 26,
    fontWeight: '700',
  },
  group: {
    marginTop: 20,
  },
  groupHeading: {
    color: '#4b534a',
    fontSize: 18,
    fontWeight: '700',
  },
  emptyText: {
    color: '#747a72',
    marginTop: 12,
  },
  seriesCard: {
    backgroundColor: '#ffffff',
    borderColor: '#dedbd2',
    borderRadius: 12,
    borderWidth: 1,
    marginTop: 12,
    padding: 16,
  },
  seriesThumbnail: {
    backgroundColor: '#eeece6',
    borderRadius: 8,
    height: 150,
    marginBottom: 14,
    width: '100%',
  },
  status: {
    color: '#315f42',
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 6,
  },
  seriesTitle: {
    color: '#20251f',
    fontSize: 20,
    fontWeight: '700',
  },
  seriesAuthor: {
    color: '#4e554e',
    fontSize: 15,
    marginTop: 3,
  },
  seriesCount: {
    color: '#343a34',
    fontWeight: '600',
    marginTop: 10,
  },
  unknownCount: {
    color: '#6a7169',
    fontSize: 13,
    marginTop: 4,
  },
  volumeList: {
    borderTopColor: '#dedbd2',
    borderTopWidth: 1,
    marginTop: 16,
  },
  volumeArea: {
    marginTop: 18,
  },
  unknownSection: {
    borderTopColor: '#dedbd2',
    borderTopWidth: 1,
    marginTop: 20,
    paddingTop: 18,
  },
  volumeHeading: {
    color: '#20251f',
    fontSize: 17,
    fontWeight: '700',
  },
  volumeCount: {
    color: '#6a7169',
    fontSize: 13,
    marginTop: 3,
  },
  toggleButton: {
    alignItems: 'center',
    borderColor: '#315f42',
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    marginTop: 12,
    minHeight: 46,
  },
  toggleText: {
    color: '#315f42',
    fontWeight: '700',
  },
  pressed: {
    opacity: 0.78,
  },
});
