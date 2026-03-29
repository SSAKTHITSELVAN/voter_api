import React, { useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';
import { LandmarkImageGallery } from '@/components/LandmarkImageGallery';
import { ThemedButton } from '@/components/ThemedButton';
import { Colors, FontSizes, Radius, Shadows, Spacing } from '@/constants/theme';
import { householdsApi, resolveApiUrl, verificationApi } from '@/lib/api';
import { Household, HouseholdBrief, VerificationStatus } from '@/lib/types';

type Step = 'search' | 'pick' | 'verify' | 'done';

export default function VerifyScreen() {
  const scrollRef = useRef<ScrollView>(null);

  const [step, setStep] = useState<Step>('search');
  const [gpsLoading, setGpsLoading] = useState(false);
  const [nearbyHouseholds, setNearbyHouseholds] = useState<HouseholdBrief[]>([]);
  const [selectedHousehold, setSelectedHousehold] = useState<HouseholdBrief | null>(null);
  const [householdDetail, setHouseholdDetail] = useState<Household | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [verifyStatus, setVerifyStatus] = useState<VerificationStatus>('MATCHED');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  async function searchNearby() {
    setErrorMsg('');
    setGpsLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setErrorMsg('Location permission is required to find nearby households.');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      const results = await householdsApi.nearby(loc.coords.latitude, loc.coords.longitude, 200, 20);
      setNearbyHouseholds(results);
      setStep('pick');
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } catch (err: any) {
      setErrorMsg(err.message ?? 'Could not get location. Please try again.');
    } finally {
      setGpsLoading(false);
    }
  }

  async function pickHousehold(household: HouseholdBrief) {
    setSelectedHousehold(household);
    setHouseholdDetail(null);
    setErrorMsg('');
    setStep('verify');
    scrollRef.current?.scrollTo({ y: 0, animated: true });

    setDetailLoading(true);
    try {
      const full = await householdsApi.get(household.id);
      setHouseholdDetail(full);
    } catch {
      setErrorMsg('Could not load household details. You can still submit verification.');
    } finally {
      setDetailLoading(false);
    }
  }

  async function submitVerification() {
    if (!selectedHousehold) return;
    setErrorMsg('');
    setSubmitting(true);
    try {
      await verificationApi.submit({
        household_id: selectedHousehold.id,
        status: verifyStatus,
        notes: notes.trim() || undefined,
      });
      setStep('done');
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } catch (err: any) {
      setErrorMsg(err.message ?? 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setStep('search');
    setNearbyHouseholds([]);
    setSelectedHousehold(null);
    setHouseholdDetail(null);
    setVerifyStatus('MATCHED');
    setNotes('');
    setErrorMsg('');
    scrollRef.current?.scrollTo({ y: 0, animated: true });
  }

  const stepIndex = step === 'done' ? 3 : ['search', 'pick', 'verify'].indexOf(step);

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView
        ref={scrollRef}
        style={styles.scroll}
        contentContainerStyle={styles.container}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.header}>
          <View style={styles.headerDecorLeft} />
          <View style={styles.headerDecorRight} />
          <View style={styles.headerContent}>
            <View style={styles.headerIconWrap}>
              <Ionicons name="checkmark-circle" size={28} color={Colors.textPrimary} />
            </View>
            <View>
              <Text style={styles.title}>Verify Household</Text>
              <Text style={styles.subtitle}>Confirm collected data and landmark images</Text>
            </View>
          </View>
        </View>

        <View style={styles.steps}>
          {['Search', 'Select', 'Verify'].map((label, index) => {
            const done = index < stepIndex || step === 'done';
            const active = index === stepIndex && step !== 'done';
            return (
              <React.Fragment key={label}>
                <View style={styles.stepItem}>
                  <View style={[styles.stepCircle, active && styles.stepCircleActive, done && styles.stepCircleDone]}>
                    {done ? (
                      <Ionicons name="checkmark" size={14} color={Colors.textPrimary} />
                    ) : (
                      <Text style={[styles.stepNum, active && styles.stepNumActive]}>{index + 1}</Text>
                    )}
                  </View>
                  <Text style={[styles.stepLabel, active && styles.stepLabelActive, done && styles.stepLabelDone]}>
                    {label}
                  </Text>
                </View>
                {index < 2 ? <View style={[styles.stepLine, done && styles.stepLineDone]} /> : null}
              </React.Fragment>
            );
          })}
        </View>

        {!!errorMsg && (
          <View style={styles.errorBanner}>
            <Ionicons name="alert-circle" size={16} color={Colors.error} />
            <Text style={styles.errorBannerText}>{errorMsg}</Text>
            <Pressable onPress={() => setErrorMsg('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
              <Ionicons name="close" size={14} color={Colors.error} />
            </Pressable>
          </View>
        )}

        {step === 'search' && (
          <View style={styles.card}>
            <View style={styles.iconBlock}>
              <Ionicons name="search-circle" size={56} color={Colors.primary} />
            </View>
            <Text style={styles.cardTitle}>Find Nearby Household</Text>
            <Text style={styles.cardDesc}>
              We will use your current GPS location to find households within 200 metres.
            </Text>
            <ThemedButton
              title={gpsLoading ? 'Locating...' : 'Find Nearby Households'}
              onPress={() => void searchNearby()}
              loading={gpsLoading}
              fullWidth
              size="lg"
              style={{ marginTop: Spacing.md }}
            />
          </View>
        )}

        {step === 'pick' && (
          <View style={styles.card}>
            <View style={styles.pickHeader}>
              <Text style={styles.cardTitle}>Select Household</Text>
              <Pressable onPress={() => setStep('search')}>
                <Text style={styles.changeBtn}>Back</Text>
              </Pressable>
            </View>

            {nearbyHouseholds.length === 0 ? (
              <View style={styles.emptyPick}>
                <Ionicons name="home-outline" size={36} color={Colors.border} />
                <Text style={styles.emptyPickText}>No households found within 200m</Text>
                <ThemedButton
                  title="Search Again"
                  onPress={() => void searchNearby()}
                  variant="outline"
                  size="sm"
                  style={{ marginTop: 12 }}
                />
              </View>
            ) : (
              <>
                <Text style={styles.pickCount}>
                  {nearbyHouseholds.length} household{nearbyHouseholds.length !== 1 ? 's' : ''} found nearby
                </Text>
                {nearbyHouseholds.map((household) => (
                  <Pressable
                    key={household.id}
                    onPress={() => void pickHousehold(household)}
                    style={({ pressed }) => [styles.pickItem, pressed && { opacity: 0.8 }]}
                  >
                    <View style={styles.pickLeft}>
                      <Ionicons
                        name={household.house_type === 'APARTMENT' ? 'business-outline' : 'home-outline'}
                        size={18}
                        color={Colors.primary}
                      />
                      <View>
                        <Text style={styles.pickAddress} numberOfLines={1}>
                          {household.address_text ?? 'No address'}
                        </Text>
                        <Text style={styles.pickDist}>
                          {household.distance_metres != null
                            ? `${Math.round(household.distance_metres)}m away · ${household.house_type}`
                            : household.house_type}
                        </Text>
                      </View>
                    </View>
                    <Ionicons name="chevron-forward" size={16} color={Colors.midGray} />
                  </Pressable>
                ))}
              </>
            )}
          </View>
        )}

        {step === 'verify' && selectedHousehold && (
          <View style={styles.card}>
            <View style={styles.pickHeader}>
              <Text style={styles.cardTitle}>Submit Verification</Text>
              <Pressable onPress={() => { setErrorMsg(''); setStep('pick'); }}>
                <Text style={styles.changeBtn}>Change</Text>
              </Pressable>
            </View>

            <View style={styles.selectedCard}>
              <Ionicons
                name={selectedHousehold.house_type === 'APARTMENT' ? 'business' : 'home'}
                size={16}
                color={selectedHousehold.house_type === 'APARTMENT' ? Colors.gold : Colors.primary}
              />
              <View style={{ flex: 1 }}>
                <Text style={styles.selectedText} numberOfLines={2}>
                  {selectedHousehold.address_text ?? `${selectedHousehold.latitude.toFixed(5)}, ${selectedHousehold.longitude.toFixed(5)}`}
                </Text>
                {selectedHousehold.distance_metres != null ? (
                  <Text style={styles.selectedDist}>
                    {Math.round(selectedHousehold.distance_metres)}m away · {selectedHousehold.house_type}
                  </Text>
                ) : null}
              </View>
            </View>

            <Text style={styles.sectionLabel}>RECORDED DATA</Text>
            {detailLoading ? (
              <View style={styles.detailLoading}>
                <ActivityIndicator size="small" color={Colors.primary} />
                <Text style={styles.detailLoadingText}>Loading household data...</Text>
              </View>
            ) : householdDetail ? (
              <HouseholdDataPanel household={householdDetail} />
            ) : (
              <View style={styles.detailUnavailable}>
                <Ionicons name="information-circle-outline" size={15} color={Colors.textMuted} />
                <Text style={styles.detailUnavailableText}>Household details unavailable</Text>
              </View>
            )}

            <Text style={[styles.fieldLabel, { marginTop: Spacing.lg }]}>Verification Status</Text>
            <View style={styles.statusRow}>
              <Pressable
                onPress={() => setVerifyStatus('MATCHED')}
                style={[styles.statusBtn, verifyStatus === 'MATCHED' && styles.statusBtnMatched]}
              >
                <Ionicons
                  name="checkmark-circle"
                  size={22}
                  color={verifyStatus === 'MATCHED' ? Colors.success : Colors.midGray}
                />
                <Text style={[styles.statusBtnText, verifyStatus === 'MATCHED' && { color: Colors.success }]}>MATCHED</Text>
                <Text style={styles.statusBtnSub}>Data is accurate</Text>
              </Pressable>
              <Pressable
                onPress={() => setVerifyStatus('MISMATCH')}
                style={[styles.statusBtn, verifyStatus === 'MISMATCH' && styles.statusBtnMismatch]}
              >
                <Ionicons
                  name="close-circle"
                  size={22}
                  color={verifyStatus === 'MISMATCH' ? Colors.error : Colors.midGray}
                />
                <Text style={[styles.statusBtnText, verifyStatus === 'MISMATCH' && { color: Colors.error }]}>MISMATCH</Text>
                <Text style={styles.statusBtnSub}>Data differs</Text>
              </Pressable>
            </View>

            <Text style={[styles.fieldLabel, { marginTop: Spacing.md }]}>Notes (optional)</Text>
            <TextInput
              style={styles.notesInput}
              value={notes}
              onChangeText={setNotes}
              placeholder="Any observations or discrepancies..."
              placeholderTextColor={Colors.midGray}
              multiline
              numberOfLines={3}
              maxLength={1000}
            />

            <ThemedButton
              title={submitting ? 'Submitting...' : 'Submit Verification'}
              onPress={() => void submitVerification()}
              loading={submitting}
              fullWidth
              size="lg"
              style={{ marginTop: Spacing.lg }}
            />
          </View>
        )}

        {step === 'done' && (
          <View style={styles.card}>
            <View style={styles.doneIcon}>
              <Ionicons
                name={verifyStatus === 'MATCHED' ? 'checkmark-circle' : 'alert-circle'}
                size={72}
                color={verifyStatus === 'MATCHED' ? Colors.success : Colors.error}
              />
            </View>

            <Text style={styles.doneTitle}>
              {verifyStatus === 'MATCHED' ? 'Verified as Matched' : 'Mismatch Recorded'}
            </Text>
            <Text style={styles.doneDesc}>
              {verifyStatus === 'MATCHED'
                ? 'The household data has been confirmed as accurate.'
                : 'A mismatch has been logged for review by an admin.'}
            </Text>

            <View
              style={[
                styles.doneSummary,
                {
                  borderColor: verifyStatus === 'MATCHED' ? Colors.success + '44' : Colors.error + '44',
                  backgroundColor: verifyStatus === 'MATCHED' ? '#0D2318' : '#200D0D',
                },
              ]}
            >
              <View style={styles.doneSummaryRow}>
                <Text style={styles.doneSummaryLabel}>Household</Text>
                <Text style={styles.doneSummaryValue} numberOfLines={1}>
                  {selectedHousehold?.address_text ?? 'No address'}
                </Text>
              </View>
              {householdDetail ? (
                <>
                  <View style={styles.doneSummaryRow}>
                    <Text style={styles.doneSummaryLabel}>Persons</Text>
                    <Text style={styles.doneSummaryValue}>{householdDetail.persons.length}</Text>
                  </View>
                  <View style={styles.doneSummaryRow}>
                    <Text style={styles.doneSummaryLabel}>Landmark Images</Text>
                    <Text style={styles.doneSummaryValue}>{householdDetail.landmark_images.length}</Text>
                  </View>
                </>
              ) : null}
              <View style={styles.doneSummaryRow}>
                <Text style={styles.doneSummaryLabel}>Status</Text>
                <Text
                  style={[
                    styles.doneSummaryValue,
                    { color: verifyStatus === 'MATCHED' ? Colors.success : Colors.error },
                  ]}
                >
                  {verifyStatus}
                </Text>
              </View>
              {!!notes.trim() && (
                <View style={styles.doneSummaryRow}>
                  <Text style={styles.doneSummaryLabel}>Notes</Text>
                  <Text style={styles.doneSummaryValue} numberOfLines={2}>{notes}</Text>
                </View>
              )}
            </View>

            <ThemedButton title="Verify Another" onPress={reset} fullWidth size="lg" style={{ marginTop: Spacing.xl }} />
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function HouseholdDataPanel({ household }: { household: Household }) {
  const totalPeople = household.persons.length;
  const voterCount = household.persons.filter((person) => person.is_voter).length;
  const nonVoterCount = totalPeople - voterCount;
  const maleCount = household.persons.filter((person) => person.gender === 'MALE').length;
  const femaleCount = household.persons.filter((person) => person.gender === 'FEMALE').length;
  const otherCount = household.persons.filter((person) => person.gender === 'OTHER').length;
  const galleryImages = household.landmark_images.map((image) => ({
    id: image.id,
    uri: resolveApiUrl(image.image_url),
  }));

  return (
    <View style={panelStyles.container}>
      <View style={panelStyles.galleryHeader}>
        <Text style={panelStyles.galleryTitle}>Landmark Images</Text>
        <Text style={panelStyles.galleryCount}>
          {household.landmark_images.length} image{household.landmark_images.length !== 1 ? 's' : ''}
        </Text>
      </View>

      <View style={panelStyles.galleryBody}>
        <LandmarkImageGallery
          images={galleryImages}
          emptyText="No landmark images available for this household."
          compact
        />
      </View>

      <View style={panelStyles.statsRow}>
        <StatChip label="Total" value={totalPeople} icon="people" color={Colors.info} />
        <StatChip label="Voters" value={voterCount} icon="checkmark-circle" color={Colors.success} />
        <StatChip label="Non-Voters" value={nonVoterCount} icon="remove-circle" color={Colors.midGray} />
      </View>

      {totalPeople > 0 ? (
        <View style={panelStyles.genderRow}>
          <GenderPill label="M" count={maleCount} color="#60A5FA" />
          <GenderPill label="F" count={femaleCount} color="#F472B6" />
          {otherCount > 0 ? <GenderPill label="O" count={otherCount} color={Colors.gold} /> : null}
        </View>
      ) : null}

      {totalPeople === 0 ? (
        <View style={panelStyles.noPerson}>
          <Text style={panelStyles.noPersonText}>No persons recorded for this household.</Text>
        </View>
      ) : (
        <View style={panelStyles.personList}>
          <Text style={panelStyles.personListTitle}>Persons ({totalPeople})</Text>
          {household.persons.map((person, index) => (
            <View key={person.id ?? index} style={panelStyles.personRow}>
              <View style={panelStyles.personBadge}>
                <Text style={panelStyles.personBadgeText}>{index + 1}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={panelStyles.personMeta}>
                  {person.gender ?? 'Unknown gender'} · Age {person.age ?? '?'}
                </Text>
              </View>
              <View
                style={[
                  panelStyles.voterTag,
                  { backgroundColor: person.is_voter ? '#16382A' : Colors.darkGray },
                ]}
              >
                <Ionicons
                  name={person.is_voter ? 'checkmark-circle' : 'close-circle'}
                  size={12}
                  color={person.is_voter ? Colors.success : Colors.midGray}
                />
                <Text style={[panelStyles.voterTagText, { color: person.is_voter ? Colors.success : Colors.midGray }]}>
                  {person.is_voter ? 'Voter' : 'Non-voter'}
                </Text>
              </View>
            </View>
          ))}
        </View>
      )}

      <View style={panelStyles.footer}>
        <Ionicons name="calendar-outline" size={11} color={Colors.textMuted} />
        <Text style={panelStyles.footerText}>
          Recorded {new Date(household.created_at).toLocaleString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}
        </Text>
      </View>
    </View>
  );
}

function StatChip({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: keyof typeof Ionicons.glyphMap;
  color: string;
}) {
  return (
    <View style={[panelStyles.statChip, { borderColor: color + '33' }]}>
      <Ionicons name={icon} size={14} color={color} />
      <Text style={[panelStyles.statValue, { color }]}>{value}</Text>
      <Text style={panelStyles.statLabel}>{label}</Text>
    </View>
  );
}

function GenderPill({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <View style={[panelStyles.genderPill, { borderColor: color + '44', backgroundColor: color + '15' }]}>
      <Text style={[panelStyles.genderPillLabel, { color }]}>{label}</Text>
      <Text style={[panelStyles.genderPillCount, { color }]}>{count}</Text>
    </View>
  );
}

const panelStyles = StyleSheet.create({
  container: {
    backgroundColor: Colors.bgDark,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    marginBottom: Spacing.md,
    overflow: 'hidden',
  },
  galleryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    gap: Spacing.sm,
  },
  galleryTitle: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '700' },
  galleryCount: { fontSize: FontSizes.xs, color: Colors.gold, fontWeight: '700' },
  galleryBody: { padding: Spacing.md, paddingTop: Spacing.sm },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, padding: Spacing.md, paddingTop: 0, paddingBottom: Spacing.sm },
  statChip: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: Spacing.sm,
    borderRadius: Radius.sm,
    borderWidth: 1,
    backgroundColor: Colors.bgCard,
    gap: 2,
  },
  statValue: { fontSize: FontSizes.lg, fontWeight: '800' },
  statLabel: {
    fontSize: 9,
    color: Colors.textMuted,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  genderRow: { flexDirection: 'row', gap: 6, paddingHorizontal: Spacing.md, paddingBottom: Spacing.sm },
  genderPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: Radius.full,
    borderWidth: 1,
  },
  genderPillLabel: { fontSize: FontSizes.xs, fontWeight: '800' },
  genderPillCount: { fontSize: FontSizes.xs, fontWeight: '700' },
  personList: { borderTopWidth: 1, borderTopColor: Colors.border, paddingTop: Spacing.sm },
  personListTitle: {
    fontSize: FontSizes.xs,
    fontWeight: '700',
    color: Colors.textMuted,
    letterSpacing: 0.5,
    paddingHorizontal: Spacing.md,
    marginBottom: 6,
    textTransform: 'uppercase',
  },
  personRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: 7,
    borderTopWidth: 1,
    borderTopColor: Colors.border + '55',
    gap: 8,
  },
  personBadge: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: Colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  personBadgeText: { fontSize: 10, fontWeight: '800', color: Colors.textPrimary },
  personMeta: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '500' },
  voterTag: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: Radius.full,
  },
  voterTagText: { fontSize: 10, fontWeight: '600' },
  noPerson: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  noPersonText: { fontSize: FontSizes.xs, color: Colors.textMuted, fontStyle: 'italic' },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    padding: Spacing.sm,
    paddingHorizontal: Spacing.md,
    borderTopWidth: 1,
    borderTopColor: Colors.border,
  },
  footerText: { fontSize: 10, color: Colors.textMuted },
});

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: Colors.bgDark },
  scroll: { flex: 1 },
  container: { paddingBottom: 56 },
  header: {
    backgroundColor: Colors.primary,
    paddingTop: 64,
    paddingHorizontal: Spacing.xl,
    paddingBottom: Spacing.xl,
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
  title: { fontSize: FontSizes.xxl, fontWeight: '900', color: Colors.textPrimary },
  subtitle: { fontSize: FontSizes.xs, color: Colors.white60, marginTop: 2 },
  steps: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: Spacing.lg,
    paddingHorizontal: Spacing.xl,
    backgroundColor: Colors.charcoal,
    borderBottomWidth: 1,
    borderBottomColor: Colors.border,
  },
  stepItem: { alignItems: 'center', gap: 5 },
  stepCircle: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: Colors.darkGray,
    borderWidth: 1.5,
    borderColor: Colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepCircleActive: { borderColor: Colors.primary, backgroundColor: Colors.primaryMuted },
  stepCircleDone: { backgroundColor: Colors.success, borderColor: Colors.success },
  stepNum: { fontSize: FontSizes.xs, fontWeight: '700', color: Colors.midGray },
  stepNumActive: { color: Colors.primary },
  stepLabel: { fontSize: 10, color: Colors.midGray, fontWeight: '600' },
  stepLabelActive: { color: Colors.primary, fontWeight: '700' },
  stepLabelDone: { color: Colors.success },
  stepLine: { flex: 1, height: 2, backgroundColor: Colors.border, marginBottom: 16, marginHorizontal: 4 },
  stepLineDone: { backgroundColor: Colors.success },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#200D0D',
    borderRadius: Radius.md,
    margin: Spacing.md,
    marginBottom: 0,
    padding: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.error + '88',
  },
  errorBannerText: { flex: 1, fontSize: FontSizes.sm, color: Colors.error, fontWeight: '500' },
  card: {
    backgroundColor: Colors.bgCard,
    margin: Spacing.md,
    marginTop: Spacing.lg,
    borderRadius: Radius.lg,
    padding: Spacing.xl,
    borderWidth: 1,
    borderColor: Colors.border,
    ...Shadows.card,
  },
  iconBlock: { alignItems: 'center', marginBottom: Spacing.md },
  cardTitle: { fontSize: FontSizes.xl, fontWeight: '800', color: Colors.textPrimary, marginBottom: 8 },
  cardDesc: { fontSize: FontSizes.sm, color: Colors.textMuted, lineHeight: 20 },
  pickHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.md },
  changeBtn: { fontSize: FontSizes.sm, color: Colors.primary, fontWeight: '700' },
  pickCount: { fontSize: FontSizes.xs, color: Colors.textMuted, marginBottom: Spacing.sm, fontWeight: '600' },
  pickItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: Colors.bgCardRaised,
    borderRadius: Radius.md,
    padding: Spacing.md,
    marginBottom: Spacing.sm,
    borderWidth: 1,
    borderColor: Colors.border,
    minHeight: 56,
  },
  pickLeft: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 10 },
  pickAddress: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '600', maxWidth: 220 },
  pickDist: { fontSize: FontSizes.xs, color: Colors.textMuted, marginTop: 2 },
  emptyPick: { alignItems: 'center', paddingVertical: Spacing.xl },
  emptyPickText: { color: Colors.textMuted, marginTop: Spacing.sm, textAlign: 'center' },
  selectedCard: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 8,
    backgroundColor: Colors.bgCardRaised,
    borderRadius: Radius.md,
    padding: Spacing.md,
    marginBottom: Spacing.md,
    borderWidth: 1.5,
    borderColor: Colors.borderRed,
  },
  selectedText: { fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '500' },
  selectedDist: { fontSize: FontSizes.xs, color: Colors.textMuted, marginTop: 2 },
  sectionLabel: {
    fontSize: FontSizes.xs,
    fontWeight: '800',
    color: Colors.textMuted,
    letterSpacing: 1,
    marginBottom: Spacing.sm,
    textTransform: 'uppercase',
  },
  detailLoading: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: Colors.bgDark,
    borderRadius: Radius.md,
    borderWidth: 1,
    borderColor: Colors.border,
    padding: Spacing.md,
    marginBottom: Spacing.md,
  },
  detailLoadingText: { fontSize: FontSizes.xs, color: Colors.textMuted },
  detailUnavailable: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: Spacing.sm, marginBottom: Spacing.md },
  detailUnavailableText: { fontSize: FontSizes.xs, color: Colors.textMuted },
  fieldLabel: { fontSize: FontSizes.xs, fontWeight: '700', color: Colors.textMuted, marginBottom: 8, letterSpacing: 0.4 },
  statusRow: { flexDirection: 'row', gap: Spacing.sm },
  statusBtn: {
    flex: 1,
    alignItems: 'center',
    padding: Spacing.md,
    borderRadius: Radius.md,
    borderWidth: 1.5,
    borderColor: Colors.border,
    backgroundColor: Colors.bgCardRaised,
    gap: 4,
    minHeight: 80,
    justifyContent: 'center',
  },
  statusBtnMatched: { borderColor: Colors.success, backgroundColor: Colors.successMuted },
  statusBtnMismatch: { borderColor: Colors.error, backgroundColor: Colors.errorMuted },
  statusBtnText: { fontSize: FontSizes.sm, fontWeight: '800', color: Colors.midGray },
  statusBtnSub: { fontSize: FontSizes.xs, color: Colors.textMuted, textAlign: 'center' },
  notesInput: {
    backgroundColor: Colors.bgCardRaised,
    borderRadius: Radius.md,
    padding: Spacing.md,
    fontSize: FontSizes.md,
    color: Colors.textPrimary,
    borderWidth: 1.5,
    borderColor: Colors.border,
    textAlignVertical: 'top',
    minHeight: 88,
  },
  doneIcon: { alignItems: 'center', marginBottom: Spacing.lg },
  doneTitle: { fontSize: FontSizes.xxl, fontWeight: '900', color: Colors.textPrimary, textAlign: 'center', marginBottom: 8 },
  doneDesc: { fontSize: FontSizes.sm, color: Colors.textMuted, textAlign: 'center', lineHeight: 22 },
  doneSummary: { width: '100%', borderRadius: Radius.md, padding: Spacing.md, borderWidth: 1, marginTop: Spacing.lg, gap: 8 },
  doneSummaryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  doneSummaryLabel: { fontSize: FontSizes.xs, color: Colors.textMuted, fontWeight: '600', minWidth: 90 },
  doneSummaryValue: { flex: 1, fontSize: FontSizes.sm, color: Colors.textPrimary, fontWeight: '700', textAlign: 'right' },
});

