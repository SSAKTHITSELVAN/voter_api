import React, { useCallback, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { useFocusEffect } from 'expo-router';
import { HouseholdCard } from '@/components/HouseholdCard';
import { LandmarkImageGallery } from '@/components/LandmarkImageGallery';
import { ThemedButton } from '@/components/ThemedButton';
import { Colors, FontSizes, Radius, Spacing } from '@/constants/theme';
import { householdsApi, resolveApiUrl } from '@/lib/api';
import { Household, HouseholdBrief } from '@/lib/types';

const RADII = [100, 250, 500, 1000, 5000];

export default function HouseholdsScreen() {
  const [households, setHouseholds] = useState<HouseholdBrief[]>([]);
  const [loading, setLoading] = useState(false);
  const [radius, setRadius] = useState(500);
  const [myLat, setMyLat] = useState<number | null>(null);
  const [myLon, setMyLon] = useState<number | null>(null);
  const [selected, setSelected] = useState<Household | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useFocusEffect(
    useCallback(() => {
      void fetchNearby();
    }, [radius]),
  );

  async function fetchNearby() {
    setLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission denied', 'Location is needed to find nearby households.');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      setMyLat(loc.coords.latitude);
      setMyLon(loc.coords.longitude);
      const results = await householdsApi.nearby(
        loc.coords.latitude,
        loc.coords.longitude,
        radius,
        100,
      );
      setHouseholds(results);
    } catch (err: any) {
      Alert.alert('Error', err.message ?? 'Could not load households.');
    } finally {
      setLoading(false);
    }
  }

  async function openHousehold(id: string) {
    setDetailLoading(true);
    try {
      const household = await householdsApi.get(id);
      setSelected(household);
    } catch (err: any) {
      Alert.alert('Error', err.message ?? 'Could not load household details.');
    } finally {
      setDetailLoading(false);
    }
  }

  if (selected) {
    return <HouseholdDetail household={selected} onBack={() => setSelected(null)} />;
  }

  return (
    <View style={styles.flex}>
      <View style={styles.header}>
        <View style={styles.headerDecorLeft} />
        <View style={styles.headerDecorRight} />
        <View style={styles.headerContent}>
          <View style={styles.headerIconWrap}>
            <Ionicons name="home" size={26} color={Colors.textPrimary} />
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.title}>Nearby Households</Text>
            {myLat !== null ? (
              <Text style={styles.subtitle}>{myLat.toFixed(4)}, {myLon?.toFixed(4)}</Text>
            ) : null}
          </View>
          <Pressable onPress={() => void fetchNearby()} style={styles.refreshHeaderBtn} disabled={loading}>
            <Ionicons name="refresh" size={20} color={loading ? Colors.white20 : Colors.textPrimary} />
          </Pressable>
        </View>
      </View>

      <View style={styles.radiusRow}>
        <Text style={styles.radiusLabel}>Radius:</Text>
        {RADII.map((value) => (
          <Pressable
            key={value}
            onPress={() => setRadius(value)}
            style={[styles.radiusBtn, radius === value && styles.radiusBtnActive]}
          >
            <Text style={[styles.radiusBtnText, radius === value && styles.radiusBtnTextActive]}>
              {value >= 1000 ? `${value / 1000}km` : `${value}m`}
            </Text>
          </Pressable>
        ))}
      </View>

      {loading || detailLoading ? (
        <View style={styles.center}>
          <ActivityIndicator color={Colors.primary} size="large" />
          <Text style={styles.loadingText}>Finding households...</Text>
        </View>
      ) : (
        <FlatList
          data={households}
          keyExtractor={(household) => household.id}
          contentContainerStyle={styles.list}
          renderItem={({ item }) => (
            <HouseholdCard household={item} onPress={() => void openHousehold(item.id)} />
          )}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Ionicons name="home-outline" size={48} color={Colors.border} />
              <Text style={styles.emptyText}>
                No households found within {radius >= 1000 ? `${radius / 1000}km` : `${radius}m`}
              </Text>
              <ThemedButton title="Refresh" onPress={() => void fetchNearby()} variant="outline" size="sm" style={{ marginTop: 16 }} />
            </View>
          }
          ListHeaderComponent={
            households.length > 0 ? (
              <Text style={styles.countText}>
                {households.length} household{households.length !== 1 ? 's' : ''} found
              </Text>
            ) : null
          }
        />
      )}
    </View>
  );
}

function HouseholdDetail({ household, onBack }: { household: Household; onBack: () => void }) {
  const voterCount = household.persons.filter((person) => person.is_voter).length;
  const galleryImages = household.landmark_images.map((image) => ({
    id: image.id,
    uri: resolveApiUrl(image.image_url),
  }));

  return (
    <View style={styles.flex}>
      <View style={styles.detailHeader}>
        <Pressable onPress={onBack} style={styles.backBtn}>
          <Ionicons name="arrow-back" size={22} color={Colors.textPrimary} />
        </Pressable>
        <Text style={styles.detailTitle}>Household Details</Text>
      </View>

      <FlatList
        data={household.persons}
        keyExtractor={(item, index) => item.id ?? String(index)}
        contentContainerStyle={styles.list}
        ListHeaderComponent={
          <>
            <View
              style={[
                styles.typeBadge,
                { borderColor: household.house_type === 'APARTMENT' ? Colors.gold : Colors.primary },
              ]}
            >
              <Ionicons
                name={household.house_type === 'APARTMENT' ? 'business' : 'home'}
                size={14}
                color={household.house_type === 'APARTMENT' ? Colors.gold : Colors.primary}
              />
              <Text
                style={[
                  styles.typeBadgeText,
                  { color: household.house_type === 'APARTMENT' ? Colors.gold : Colors.primary },
                ]}
              >
                {household.house_type}
              </Text>
            </View>

            <View style={styles.detailCard}>
              <Row icon="location-outline" label="Address" value={household.address_text ?? 'N/A'} />
              <Row
                icon="navigate-outline"
                label="Coordinates"
                value={`${household.latitude.toFixed(6)}, ${household.longitude.toFixed(6)}`}
                mono
              />
              <Row
                icon="calendar-outline"
                label="Recorded On"
                value={new Date(household.created_at).toLocaleString('en-IN')}
              />
            </View>

            <View style={styles.gallerySection}>
              <View style={styles.galleryHeader}>
                <Text style={styles.galleryTitle}>Landmark Images</Text>
                <Text style={styles.galleryCount}>
                  {household.landmark_images.length} image{household.landmark_images.length !== 1 ? 's' : ''}
                </Text>
              </View>
              <LandmarkImageGallery
                images={galleryImages}
                emptyText="No landmark images were uploaded for this household."
              />
            </View>

            <View style={styles.statsRow}>
              <StatMini label="Total People" value={household.persons.length} color={Colors.info} />
              <StatMini label="Voters" value={voterCount} color={Colors.success} />
              <StatMini label="Non-Voters" value={household.persons.length - voterCount} color={Colors.lightGray} />
            </View>

            <Text style={styles.personsTitle}>Persons ({household.persons.length})</Text>
          </>
        }
        renderItem={({ item, index }) => (
          <View style={styles.personRow}>
            <View style={styles.personBadge}>
              <Text style={styles.personBadgeText}>{index + 1}</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.personInfo}>
                {item.gender ?? 'Unknown'} · Age {item.age ?? '?'}
              </Text>
            </View>
            <View style={[styles.voterTag, { backgroundColor: item.is_voter ? '#16382A' : Colors.darkGray }]}>
              <Ionicons
                name={item.is_voter ? 'checkmark-circle' : 'close-circle'}
                size={13}
                color={item.is_voter ? Colors.success : Colors.midGray}
              />
              <Text style={[styles.voterTagText, { color: item.is_voter ? Colors.success : Colors.midGray }]}>
                {item.is_voter ? 'Voter' : 'Non-voter'}
              </Text>
            </View>
          </View>
        )}
        ListEmptyComponent={<Text style={styles.noPerson}>No persons recorded.</Text>}
      />
    </View>
  );
}

function Row({
  icon,
  label,
  value,
  mono,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <View style={styles.rowItem}>
      <Ionicons name={icon} size={15} color={Colors.primary} style={{ marginTop: 2 }} />
      <View style={{ flex: 1 }}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={[styles.rowValue, mono && { fontFamily: 'monospace', fontSize: FontSizes.xs }]}>
          {value}
        </Text>
      </View>
    </View>
  );
}

function StatMini({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={[styles.statMini, { borderColor: color + '44' }]}>
      <Text style={[styles.statMiniValue, { color }]}>{value}</Text>
      <Text style={styles.statMiniLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: Colors.bgDark },
  header: {
    backgroundColor: Colors.primary,
    paddingTop: 64,
    paddingHorizontal: Spacing.xl,
    paddingBottom: Spacing.lg,
    overflow: 'hidden',
  },
  headerDecorLeft: {
    position: 'absolute',
    top: -20,
    left: -20,
    width: 120,
    height: 120,
    borderRadius: 60,
    backgroundColor: Colors.primaryDark,
    opacity: 0.5,
  },
  headerDecorRight: {
    position: 'absolute',
    bottom: -30,
    right: -20,
    width: 160,
    height: 160,
    borderRadius: 80,
    backgroundColor: Colors.primaryDark,
    opacity: 0.4,
  },
  headerContent: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  headerIconWrap: {
    width: 48,
    height: 48,
    borderRadius: Radius.md,
    backgroundColor: Colors.white10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  refreshHeaderBtn: {
    width: 44,
    height: 44,
    borderRadius: Radius.md,
    backgroundColor: Colors.white10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: { fontSize: FontSizes.xxl, fontWeight: '900', color: Colors.textPrimary },
  subtitle: { fontSize: FontSizes.xs, color: Colors.white60, marginTop: 2 },
  radiusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    backgroundColor: Colors.charcoal,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  radiusLabel: { fontSize: FontSizes.xs, color: Colors.textMuted, fontWeight: '600' },
  radiusBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: Radius.full,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  radiusBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  radiusBtnText: { fontSize: FontSizes.xs, color: Colors.midGray, fontWeight: '600' },
  radiusBtnTextActive: { color: Colors.textPrimary },
  list: { padding: Spacing.md, paddingBottom: 32 },
  countText: { fontSize: FontSizes.xs, color: Colors.textMuted, marginBottom: Spacing.sm, fontWeight: '600' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  loadingText: { color: Colors.textMuted, marginTop: Spacing.md, fontSize: FontSizes.sm },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', paddingTop: 80 },
  emptyText: { color: Colors.textMuted, marginTop: Spacing.md, textAlign: 'center', fontSize: FontSizes.sm },
  detailHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.charcoal,
    paddingTop: 56,
    paddingBottom: Spacing.md,
    paddingHorizontal: Spacing.lg,
    gap: Spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  backBtn: { padding: 4 },
  detailTitle: { fontSize: FontSizes.lg, fontWeight: '700', color: Colors.textPrimary },
  typeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    marginHorizontal: Spacing.md,
    marginTop: Spacing.md,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: Radius.full,
    borderWidth: 1.5,
  },
  typeBadgeText: { fontSize: FontSizes.xs, fontWeight: '700' },
  detailCard: {
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    margin: Spacing.md,
    marginTop: Spacing.sm,
    padding: Spacing.md,
    gap: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
  },
  rowItem: { flexDirection: 'row', gap: 10, alignItems: 'flex-start' },
  rowLabel: { fontSize: FontSizes.xs, color: Colors.textMuted, marginBottom: 2 },
  rowValue: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '500' },
  gallerySection: {
    marginHorizontal: Spacing.md,
    marginBottom: Spacing.md,
    gap: Spacing.sm,
  },
  galleryHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  galleryTitle: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '700' },
  galleryCount: { fontSize: FontSizes.xs, color: Colors.gold, fontWeight: '700' },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginHorizontal: Spacing.md, marginBottom: Spacing.md },
  statMini: {
    flex: 1,
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    padding: Spacing.md,
    alignItems: 'center',
    borderWidth: 1,
  },
  statMiniValue: { fontSize: FontSizes.xl, fontWeight: '800' },
  statMiniLabel: { fontSize: FontSizes.xs, color: Colors.textMuted, marginTop: 2, textAlign: 'center' },
  personsTitle: { fontSize: FontSizes.md, fontWeight: '700', color: Colors.textPrimary, marginHorizontal: Spacing.md, marginBottom: Spacing.sm },
  personRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgCard,
    borderRadius: Radius.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    gap: 10,
    borderWidth: 1,
    borderColor: Colors.border,
    marginHorizontal: Spacing.md,
  },
  personBadge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  personBadgeText: { fontSize: FontSizes.xs, fontWeight: '700', color: Colors.textPrimary },
  personInfo: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '500' },
  voterTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: Radius.full,
  },
  voterTagText: { fontSize: FontSizes.xs, fontWeight: '600' },
  noPerson: { textAlign: 'center', color: Colors.textMuted, padding: Spacing.xl },
});

