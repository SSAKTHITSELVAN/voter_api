import React, { useRef, useState } from 'react';
import {
  Alert,
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
import { Colors, FontSizes, Radius, Shadows, Spacing } from '@/constants/theme';
import { ThemedButton } from '@/components/ThemedButton';
import { householdsApi } from '@/lib/api';
import { GenderType, HouseType, HouseholdCreate } from '@/lib/types';

interface DraftPerson {
  age: string;
  gender: GenderType | null;
  is_voter: boolean;
}

interface DraftHousehold {
  id: string;
  latitude: string;
  longitude: string;
  address_text: string;
  house_type: HouseType;
  persons: DraftPerson[];
  gpsAcquired: boolean;
}

let _draftId = 1;
function newDraft(): DraftHousehold {
  return {
    id: String(_draftId++),
    latitude: '',
    longitude: '',
    address_text: '',
    house_type: 'INDIVIDUAL',
    persons: [{ age: '', gender: null, is_voter: false }],
    gpsAcquired: false,
  };
}

type ResultState = {
  total: number;
  created: number;
  duplicates_skipped: number;
  errors: { index: number; detail: string }[];
} | null;

export default function BulkScreen() {
  const scrollRef = useRef<ScrollView>(null);
  const [drafts, setDrafts] = useState<DraftHousehold[]>([newDraft()]);
  const [gpsLoading, setGpsLoading] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<ResultState>(null);

  // Inline error banner
  const [errorMsg, setErrorMsg] = useState('');

  // â”€â”€ GPS per draft â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  async function getGpsForDraft(id: string) {
    setGpsLoading(id);
    setErrorMsg('');
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setErrorMsg('Location permission required to get GPS coordinates.');
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      updateDraft(id, {
        latitude: loc.coords.latitude.toFixed(7),
        longitude: loc.coords.longitude.toFixed(7),
        gpsAcquired: true,
      });
    } catch {
      setErrorMsg('Could not acquire GPS. Please try again or enter coordinates manually.');
    } finally {
      setGpsLoading(null);
    }
  }

  function updateDraft(id: string, patch: Partial<DraftHousehold>) {
    setDrafts(prev => prev.map(d => d.id === id ? { ...d, ...patch } : d));
  }

  function updatePerson(draftId: string, pIdx: number, patch: Partial<DraftPerson>) {
    setDrafts(prev => prev.map(d => {
      if (d.id !== draftId) return d;
      const persons = d.persons.map((p, i) => i === pIdx ? { ...p, ...patch } : p);
      return { ...d, persons };
    }));
  }

  function addPerson(draftId: string) {
    setDrafts(prev => prev.map(d =>
      d.id === draftId ? { ...d, persons: [...d.persons, { age: '', gender: null, is_voter: false }] } : d
    ));
  }

  function removePerson(draftId: string, pIdx: number) {
    setDrafts(prev => prev.map(d =>
      d.id === draftId ? { ...d, persons: d.persons.filter((_, i) => i !== pIdx) } : d
    ));
  }

  function addDraft() {
    if (drafts.length >= 50) {
      Alert.alert('Limit', 'Maximum 50 households per batch.');
      return;
    }
    setDrafts(prev => [...prev, newDraft()]);
  }

  function removeDraft(id: string) {
    if (drafts.length === 1) return;
    setDrafts(prev => prev.filter(d => d.id !== id));
  }

  async function handleSubmit() {
    setErrorMsg('');

    // Validate â€” find first missing GPS
    for (let i = 0; i < drafts.length; i++) {
      const d = drafts[i];
      if (!d.latitude || !d.longitude) {
        setErrorMsg(`Household #${i + 1} is missing GPS coordinates. Tap "Get GPS" on that card.`);
        scrollRef.current?.scrollTo({ y: 0, animated: true });
        return;
      }
    }

    setSubmitting(true);
    setResult(null);
    try {
      const payload: HouseholdCreate[] = drafts.map(d => ({
        latitude: parseFloat(d.latitude),
        longitude: parseFloat(d.longitude),
        address_text: d.address_text.trim() || undefined,
        house_type: d.house_type,
        persons: d.persons.map(p => ({
          age: p.age ? parseInt(p.age) : null,
          gender: p.gender,
          is_voter: p.is_voter,
        })),
        landmark_image_urls: [],
      }));

      const res = await householdsApi.bulk(payload);
      setResult(res);
      // Only reset drafts if at least one was created
      if (res.created > 0) {
        setDrafts([newDraft()]);
      }
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } catch (err: any) {
      setErrorMsg(err.message ?? 'Upload failed. Please check your connection and try again.');
      scrollRef.current?.scrollTo({ y: 0, animated: true });
    } finally {
      setSubmitting(false);
    }
  }

  // â”€â”€ Result Screen â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  if (result) {
    const allGood = result.errors.length === 0;
    const hasSkipped = result.duplicates_skipped > 0;

    return (
      <View style={styles.flex}>
        <View style={styles.header}>
          <View style={styles.headerDecorLeft} />
          <View style={styles.headerDecorRight} />
          <View style={styles.headerContent}>
            <View style={styles.headerIconWrap}>
              <Ionicons name="cloud-upload" size={26} color={Colors.textPrimary} />
            </View>
            <Text style={styles.title}>Bulk Upload</Text>
          </View>
        </View>

        <ScrollView contentContainerStyle={styles.resultContainer}>
          <View style={styles.resultCard}>
            <Ionicons
              name={allGood ? 'cloud-done' : 'alert-circle'}
              size={64}
              color={allGood ? Colors.success : Colors.warning}
            />
            <Text style={styles.resultTitle}>Upload Complete</Text>

            <View style={styles.resultGrid}>
              <ResultStat label="Total Sent"    value={result.total}                 color={Colors.info}    />
              <ResultStat label="Created"       value={result.created}               color={Colors.success} />
              <ResultStat label="Duplicates"    value={result.duplicates_skipped}    color={Colors.warning} />
              <ResultStat label="Errors"        value={result.errors.length}         color={Colors.error}   />
            </View>

            {/* Informational messages */}
            {result.created > 0 && (
              <View style={styles.resultMsg}>
                <Ionicons name="checkmark-circle" size={16} color={Colors.success} />
                <Text style={[styles.resultMsgText, { color: Colors.success }]}>
                  {result.created} household{result.created !== 1 ? 's' : ''} recorded successfully.
                </Text>
              </View>
            )}
            {hasSkipped && (
              <View style={styles.resultMsg}>
                <Ionicons name="copy-outline" size={16} color={Colors.warning} />
                <Text style={[styles.resultMsgText, { color: Colors.warning }]}>
                  {result.duplicates_skipped} skipped â€” already exist within 20m of an existing household.
                </Text>
              </View>
            )}
            {result.created === 0 && result.errors.length === 0 && (
              <View style={styles.resultMsg}>
                <Ionicons name="information-circle" size={16} color={Colors.info} />
                <Text style={[styles.resultMsgText, { color: Colors.info }]}>
                  All submitted households were duplicates. No new records were created.
                </Text>
              </View>
            )}

            {/* Error list */}
            {result.errors.length > 0 && (
              <View style={styles.errorList}>
                <Text style={styles.errorTitle}>
                  âš ï¸ {result.errors.length} Error{result.errors.length !== 1 ? 's' : ''}
                </Text>
                {result.errors.map(e => (
                  <View key={e.index} style={styles.errorItem}>
                    <Text style={styles.errorIdx}>#{e.index + 1}</Text>
                    <Text style={styles.errorDetail}>{e.detail}</Text>
                  </View>
                ))}
              </View>
            )}

            <ThemedButton
              title="Upload More"
              onPress={() => { setResult(null); setDrafts([newDraft()]); }}
              fullWidth
              size="lg"
              style={{ marginTop: Spacing.xl }}
            />
          </View>
        </ScrollView>
      </View>
    );
  }

  // â”€â”€ Main Form â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  return (
    <View style={styles.flex}>
      <View style={styles.header}>
        <View style={styles.headerDecorLeft} />
        <View style={styles.headerDecorRight} />
        <View style={styles.headerContent}>
          <View style={styles.headerIconWrap}>
            <Ionicons name="cloud-upload" size={26} color={Colors.textPrimary} />
          </View>
          <View>
            <Text style={styles.title}>Bulk Upload</Text>
            <Text style={styles.subtitle}>Sync offline-collected households</Text>
          </View>
        </View>
      </View>

      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.container}
          keyboardShouldPersistTaps="handled"
        >

          {/* â”€â”€ Inline error banner â”€â”€ */}
          {!!errorMsg && (
            <View style={styles.errorBanner}>
              <Ionicons name="alert-circle" size={16} color={Colors.error} />
              <Text style={styles.errorBannerText}>{errorMsg}</Text>
              <Pressable onPress={() => setErrorMsg('')} hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
                <Ionicons name="close" size={14} color={Colors.error} />
              </Pressable>
            </View>
          )}

          <View style={styles.infoBar}>
            <Ionicons name="information-circle-outline" size={16} color={Colors.info} />
            <Text style={styles.infoText}>
              {drafts.length} household{drafts.length !== 1 ? 's' : ''} queued Â· Duplicates within 20m are auto-skipped
            </Text>
          </View>

          {drafts.map((draft, dIdx) => (
            <View key={draft.id} style={styles.draftCard}>
              {/* Draft header */}
              <View style={styles.draftHeader}>
                <View style={styles.draftNumBadge}>
                  <Text style={styles.draftNum}>{dIdx + 1}</Text>
                </View>
                <Text style={styles.draftTitle}>Household #{dIdx + 1}</Text>
                {drafts.length > 1 && (
                  <Pressable onPress={() => removeDraft(draft.id)}>
                    <Ionicons name="trash-outline" size={18} color={Colors.error} />
                  </Pressable>
                )}
              </View>

              {/* GPS row */}
              <View style={[styles.gpsRow, draft.gpsAcquired && styles.gpsRowDone]}>
                <Ionicons
                  name="navigate"
                  size={15}
                  color={draft.gpsAcquired ? Colors.success : Colors.primary}
                />
                {draft.gpsAcquired ? (
                  <Text style={styles.gpsText}>
                    {parseFloat(draft.latitude).toFixed(5)}, {parseFloat(draft.longitude).toFixed(5)}
                  </Text>
                ) : (
                  <Text style={styles.gpsEmpty}>No location set</Text>
                )}
                <Pressable
                  onPress={() => getGpsForDraft(draft.id)}
                  style={styles.gpsBtn}
                  disabled={gpsLoading === draft.id}
                >
                  <Text style={styles.gpsBtnText}>
                    {gpsLoading === draft.id ? 'Locatingâ€¦' : draft.gpsAcquired ? 'Refresh' : 'Get GPS'}
                  </Text>
                </Pressable>
              </View>

              {/* Address */}
              <TextInput
                style={styles.addressInput}
                value={draft.address_text}
                onChangeText={v => updateDraft(draft.id, { address_text: v })}
                placeholder="Address (optional)"
                placeholderTextColor={Colors.midGray}
              />

              {/* House Type */}
              <View style={styles.typeRow}>
                {(['INDIVIDUAL', 'APARTMENT'] as HouseType[]).map(t => (
                  <Pressable
                    key={t}
                    onPress={() => updateDraft(draft.id, { house_type: t })}
                    style={[styles.typeBtn, draft.house_type === t && styles.typeBtnActive]}
                  >
                    <Text style={[styles.typeBtnText, draft.house_type === t && styles.typeBtnTextActive]}>
                      {t}
                    </Text>
                  </Pressable>
                ))}
              </View>

              {/* Persons */}
              <View style={styles.personsSection}>
                <View style={styles.personsTop}>
                  <Text style={styles.personsLabel}>
                    Persons ({draft.persons.length}) Â· {draft.persons.filter(p => p.is_voter).length} voter{draft.persons.filter(p => p.is_voter).length !== 1 ? 's' : ''}
                  </Text>
                  <Pressable onPress={() => addPerson(draft.id)} style={styles.addPersonBtn}>
                    <Ionicons name="add" size={14} color={Colors.primary} />
                    <Text style={styles.addPersonText}>Add</Text>
                  </Pressable>
                </View>
                {draft.persons.map((p, pIdx) => (
                  <View key={pIdx} style={styles.personRow}>
                    <TextInput
                      style={styles.ageInput}
                      value={p.age}
                      onChangeText={v => updatePerson(draft.id, pIdx, { age: v })}
                      placeholder="Age"
                      placeholderTextColor={Colors.midGray}
                      keyboardType="numeric"
                      maxLength={3}
                    />
                    {(['M', 'F', 'O'] as const).map(g => {
                      const full: GenderType = g === 'M' ? 'MALE' : g === 'F' ? 'FEMALE' : 'OTHER';
                      return (
                        <Pressable
                          key={g}
                          onPress={() => updatePerson(draft.id, pIdx, { gender: full })}
                          style={[styles.genderBtn, p.gender === full && styles.genderBtnActive]}
                        >
                          <Text style={[styles.genderText, p.gender === full && styles.genderTextActive]}>{g}</Text>
                        </Pressable>
                      );
                    })}
                    <Pressable
                      onPress={() => updatePerson(draft.id, pIdx, { is_voter: !p.is_voter })}
                      style={[styles.voterBtn, p.is_voter && styles.voterBtnActive]}
                    >
                      <Ionicons
                        name={p.is_voter ? 'checkmark' : 'close'}
                        size={12}
                        color={p.is_voter ? Colors.textPrimary : Colors.midGray}
                      />
                      <Text style={[styles.voterBtnText, p.is_voter && styles.voterBtnTextActive]}>
                        {p.is_voter ? 'Voter' : 'Non'}
                      </Text>
                    </Pressable>
                    {draft.persons.length > 1 && (
                      <Pressable onPress={() => removePerson(draft.id, pIdx)}>
                        <Ionicons name="close-circle-outline" size={18} color={Colors.error} />
                      </Pressable>
                    )}
                  </View>
                ))}
              </View>
            </View>
          ))}

          {/* Add more */}
          <Pressable onPress={addDraft} style={styles.addDraftBtn}>
            <Ionicons name="add-circle-outline" size={20} color={Colors.primary} />
            <Text style={styles.addDraftText}>Add Another Household</Text>
          </Pressable>

          {/* Submit */}
          <ThemedButton
            title={submitting ? 'Uploadingâ€¦' : `Upload ${drafts.length} Household${drafts.length !== 1 ? 's' : ''}`}
            onPress={handleSubmit}
            loading={submitting}
            fullWidth
            size="lg"
            style={{ marginTop: Spacing.sm }}
          />
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

function ResultStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={[styles.resultStat, { borderColor: color + '44' }]}>
      <Text style={[styles.resultStatValue, { color }]}>{value}</Text>
      <Text style={styles.resultStatLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1, backgroundColor: Colors.bgDark },
  header: {
    backgroundColor: Colors.primary,
    paddingTop: 64, paddingHorizontal: Spacing.xl, paddingBottom: Spacing.lg,
    overflow: 'hidden',
  },
  headerDecorLeft: {
    position: 'absolute', top: -20, left: -20,
    width: 120, height: 120, borderRadius: 60,
    backgroundColor: Colors.primaryDark, opacity: 0.5,
  },
  headerDecorRight: {
    position: 'absolute', bottom: -30, right: -20,
    width: 160, height: 160, borderRadius: 80,
    backgroundColor: Colors.primaryDark, opacity: 0.4,
  },
  headerContent: { flexDirection: 'row', alignItems: 'center', gap: Spacing.md },
  headerIconWrap: {
    width: 48, height: 48, borderRadius: Radius.md,
    backgroundColor: Colors.white10,
    alignItems: 'center', justifyContent: 'center',
  },
  title: { fontSize: FontSizes.xxl, fontWeight: '900', color: Colors.textPrimary },
  subtitle: { fontSize: FontSizes.xs, color: Colors.white60, marginTop: 2 },
  container: { padding: Spacing.md, paddingBottom: 56 },

  // Inline error banner
  errorBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#200D0D', borderRadius: Radius.md,
    padding: Spacing.md, marginBottom: Spacing.sm,
    borderWidth: 1.5, borderColor: Colors.error + '88',
  },
  errorBannerText: { flex: 1, fontSize: FontSizes.sm, color: Colors.error, fontWeight: '500' },

  infoBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: '#0D1A2A', borderRadius: Radius.md,
    padding: Spacing.md, marginBottom: Spacing.md,
    borderWidth: 1, borderColor: Colors.info + '44',
  },
  infoText: { flex: 1, fontSize: FontSizes.sm, color: Colors.info },

  draftCard: {
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    padding: Spacing.md, marginBottom: Spacing.md,
    borderWidth: 1, borderColor: Colors.border,
  },
  draftHeader: {
    flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: Spacing.md,
  },
  draftNumBadge: {
    width: 28, height: 28, borderRadius: 14,
    backgroundColor: Colors.primary, alignItems: 'center', justifyContent: 'center',
  },
  draftNum: { fontSize: FontSizes.sm, fontWeight: '700', color: Colors.textPrimary },
  draftTitle: { flex: 1, fontSize: FontSizes.md, fontWeight: '700', color: Colors.textPrimary },

  gpsRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: Colors.darkGray, borderRadius: Radius.sm,
    padding: Spacing.sm, marginBottom: Spacing.sm,
    borderWidth: 1, borderColor: Colors.border,
  },
  gpsRowDone: { borderColor: Colors.success + '66' },
  gpsText: { flex: 1, fontSize: FontSizes.xs, color: Colors.success, fontFamily: 'monospace' },
  gpsEmpty: { flex: 1, fontSize: FontSizes.xs, color: Colors.textMuted },
  gpsBtn: {
    paddingHorizontal: 10, paddingVertical: 4,
    borderRadius: Radius.full, backgroundColor: Colors.primary + '22',
    borderWidth: 1, borderColor: Colors.primary,
  },
  gpsBtnText: { fontSize: FontSizes.xs, color: Colors.primary, fontWeight: '600' },

  addressInput: {
    backgroundColor: Colors.darkGray, borderRadius: Radius.sm,
    paddingHorizontal: Spacing.md, paddingVertical: 10,
    fontSize: FontSizes.sm, color: Colors.textPrimary,
    borderWidth: 1, borderColor: Colors.border, marginBottom: Spacing.sm,
  },

  typeRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  typeBtn: {
    flex: 1, paddingVertical: 8, alignItems: 'center',
    borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.darkGray,
  },
  typeBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  typeBtnText: { fontSize: FontSizes.sm, fontWeight: '600', color: Colors.midGray },
  typeBtnTextActive: { color: Colors.textPrimary },

  personsSection: {},
  personsTop: {
    flexDirection: 'row', justifyContent: 'space-between',
    alignItems: 'center', marginBottom: 8,
  },
  personsLabel: { fontSize: FontSizes.xs, fontWeight: '600', color: Colors.textMuted },
  addPersonBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    paddingHorizontal: 8, paddingVertical: 4,
    borderRadius: Radius.full, borderWidth: 1, borderColor: Colors.primary,
  },
  addPersonText: { fontSize: FontSizes.xs, color: Colors.primary, fontWeight: '600' },
  personRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 6 },
  ageInput: {
    width: 48, height: 34,
    backgroundColor: Colors.darkGray, borderRadius: Radius.sm,
    paddingHorizontal: 6, fontSize: FontSizes.sm, color: Colors.textPrimary,
    borderWidth: 1, borderColor: Colors.border, textAlign: 'center',
  },
  genderBtn: {
    width: 30, height: 34, alignItems: 'center', justifyContent: 'center',
    borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.darkGray,
  },
  genderBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  genderText: { fontSize: FontSizes.xs, fontWeight: '700', color: Colors.midGray },
  genderTextActive: { color: Colors.textPrimary },
  voterBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 3,
    paddingHorizontal: 8, height: 34,
    borderRadius: Radius.sm, borderWidth: 1, borderColor: Colors.border,
    backgroundColor: Colors.darkGray,
  },
  voterBtnActive: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  voterBtnText: { fontSize: FontSizes.xs, fontWeight: '600', color: Colors.midGray },
  voterBtnTextActive: { color: Colors.textPrimary },

  addDraftBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, padding: Spacing.md,
    borderRadius: Radius.md, borderWidth: 1.5,
    borderColor: Colors.primary, borderStyle: 'dashed',
    marginBottom: Spacing.md,
  },
  addDraftText: { fontSize: FontSizes.sm, color: Colors.primary, fontWeight: '600' },

  // Result screen
  resultContainer: { padding: Spacing.md, paddingBottom: 48 },
  resultCard: {
    backgroundColor: Colors.bgCard, borderRadius: Radius.lg,
    padding: Spacing.xl, alignItems: 'center',
    borderWidth: 1, borderColor: Colors.border,
  },
  resultTitle: {
    fontSize: FontSizes.xl, fontWeight: '800', color: Colors.textPrimary,
    marginTop: Spacing.md, marginBottom: Spacing.lg,
  },
  resultGrid: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 10,
    justifyContent: 'center', marginBottom: Spacing.md, width: '100%',
  },
  resultStat: {
    width: '44%', backgroundColor: Colors.darkGray,
    borderRadius: Radius.md, padding: Spacing.md, alignItems: 'center',
    borderWidth: 1,
  },
  resultStatValue: { fontSize: FontSizes.xxl, fontWeight: '800' },
  resultStatLabel: { fontSize: FontSizes.xs, color: Colors.textMuted, marginTop: 4 },

  resultMsg: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 8,
    width: '100%', marginBottom: 6,
  },
  resultMsgText: { flex: 1, fontSize: FontSizes.sm, fontWeight: '500', lineHeight: 18 },

  errorList: {
    width: '100%', backgroundColor: '#200D0D',
    borderRadius: Radius.md, padding: Spacing.md,
    borderWidth: 1, borderColor: Colors.error + '44',
    marginTop: Spacing.sm,
  },
  errorTitle: { fontSize: FontSizes.sm, fontWeight: '700', color: Colors.error, marginBottom: 8 },
  errorItem: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  errorIdx: { fontSize: FontSizes.xs, color: Colors.error, fontWeight: '700', minWidth: 24 },
  errorDetail: { flex: 1, fontSize: FontSizes.xs, color: Colors.textMuted },
});
