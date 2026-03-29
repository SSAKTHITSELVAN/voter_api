import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { Colors, FontSizes, Radius, Spacing } from '@/constants/theme';

export interface LandmarkGalleryItem {
  id?: string;
  uri: string;
}

interface LandmarkImageGalleryProps {
  images: LandmarkGalleryItem[];
  emptyText?: string;
  compact?: boolean;
  onRemove?: (index: number) => void;
}

export function LandmarkImageGallery({
  images,
  emptyText = 'No landmark images added yet.',
  compact = false,
  onRemove,
}: LandmarkImageGalleryProps) {
  if (images.length === 0) {
    return (
      <View style={[styles.emptyState, compact && styles.emptyStateCompact]}>
        <Ionicons name="image-outline" size={16} color={Colors.textMuted} />
        <Text style={styles.emptyText}>{emptyText}</Text>
      </View>
    );
  }

  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.row}
    >
      {images.map((image, index) => (
        <View
          key={image.id ?? `${image.uri}-${index}`}
          style={[styles.card, compact && styles.cardCompact]}
        >
          <Image
            source={{ uri: image.uri }}
            style={[styles.image, compact && styles.imageCompact]}
            contentFit="cover"
            transition={150}
          />
          {onRemove ? (
            <Pressable
              onPress={() => onRemove(index)}
              style={styles.removeButton}
              hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            >
              <Ionicons name="close" size={14} color={Colors.textPrimary} />
            </Pressable>
          ) : null}
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  row: {
    gap: Spacing.sm,
  },
  card: {
    width: 148,
    height: 148,
    borderRadius: Radius.md,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: Colors.border,
    backgroundColor: Colors.bgCardRaised,
  },
  cardCompact: {
    width: 112,
    height: 112,
  },
  image: {
    width: '100%',
    height: '100%',
    backgroundColor: Colors.darkGray,
  },
  imageCompact: {
    height: '100%',
  },
  removeButton: {
    position: 'absolute',
    top: Spacing.xs,
    right: Spacing.xs,
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.bgOverlay,
    borderWidth: 1,
    borderColor: Colors.white20,
  },
  emptyState: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    minHeight: 68,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    borderStyle: 'dashed',
    paddingHorizontal: Spacing.md,
    backgroundColor: Colors.bgCardRaised,
  },
  emptyStateCompact: {
    minHeight: 56,
  },
  emptyText: {
    flex: 1,
    color: Colors.textMuted,
    fontSize: FontSizes.xs,
  },
});
