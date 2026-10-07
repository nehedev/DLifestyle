import { MaterialCommunityIcons } from '@expo/vector-icons'
import { router, useLocalSearchParams } from 'expo-router'
import { useCallback, useEffect, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  Linking,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'
import { cancelServiceRequest, naira, type ServiceRequestResponse } from '@/api'
import { PHONE } from '@/data'
import { C } from '@/theme'

// Fetch isn't exposed as a standalone function in api.ts, so we do a thin
// inline call here reusing the same request helper pattern.
import { request } from '@/api'

const CANCELLABLE = ['requested', 'contacted']

const STATUS_LABELS: Record<string, string> = {
  requested: 'Received',
  contacted: 'We contacted you',
  quoted: 'Quote sent',
  accepted: 'Quote accepted',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

function statusLabel(s: string) {
  return STATUS_LABELS[s] ?? s
}

function badgeBg(s: string) {
  if (s === 'cancelled') return C.burg
  if (s === 'completed') return C.green
  if (s === 'quoted' || s === 'accepted') return '#0A6A1B'
  return '#B8791F'
}

export default function ServiceDetailScreen() {
  const { requestId } = useLocalSearchParams<{ requestId: string }>()
  const id = Number(requestId)

  const [req, setReq] = useState<ServiceRequestResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [cancelling, setCancelling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await request<ServiceRequestResponse>(`/api/v1/service-requests/${id}`)
      setReq(data)
    } catch {
      setError('We could not load that service request.')
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    void load()
  }, [load])

  const handleCancel = () => {
    Alert.alert('Cancel this request?', 'This cannot be undone.', [
      { text: 'Keep it', style: 'cancel' },
      {
        text: 'Cancel request',
        style: 'destructive',
        onPress: async () => {
          setCancelling(true)
          try {
            setReq(await cancelServiceRequest(id))
          } catch {
            Alert.alert('Could not cancel', 'That request can no longer be cancelled.')
          } finally {
            setCancelling(false)
          }
        },
      },
    ])
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={C.green} size="large" />
      </View>
    )
  }

  if (error || !req) {
    return (
      <View style={styles.center}>
        <Text style={styles.errTxt}>{error || 'Request not found.'}</Text>
        <Pressable style={styles.btn} onPress={() => router.back()}>
          <Text style={styles.btnTxt}>Go back</Text>
        </Pressable>
      </View>
    )
  }

  const canCancel = CANCELLABLE.includes(req.status)
  const bg = badgeBg(req.status)

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: C.cream }}
      contentContainerStyle={{ padding: 20, paddingBottom: 60 }}
    >
      {/* Status banner */}
      <View style={[styles.banner, { backgroundColor: bg }]}>
        <MaterialCommunityIcons name="tools" size={28} color="#fff" />
        <View style={{ flex: 1 }}>
          <Text style={styles.bannerTitle}>Service request #{req.id}</Text>
          <Text style={styles.bannerSub}>{statusLabel(req.status)}</Text>
        </View>
      </View>

      {/* Quote highlight — shown prominently when a quote has been sent */}
      {req.quoted_amount_minor != null && (
        <View style={styles.quoteCard}>
          <Text style={styles.quoteLabel}>Our quote</Text>
          <Text style={styles.quoteAmount}>{naira(req.quoted_amount_minor)}</Text>
          {req.owner_note ? (
            <Text style={styles.quoteNote}>{req.owner_note}</Text>
          ) : null}
        </View>
      )}

      {/* Request details */}
      <View style={styles.section}>
        <Text style={styles.sectionH}>Request details</Text>
        <DetailRow label="Location" value={req.location} />
        <DetailRow label="What's needed" value={req.details} />
        {req.preferred_date ? (
          <DetailRow label="Preferred date" value={req.preferred_date} />
        ) : null}
        <DetailRow label="Contact phone" value={req.contact_phone} />
        <DetailRow label="Submitted" value={new Date(req.created_at).toLocaleDateString('en-NG', { day: 'numeric', month: 'short', year: 'numeric' })} />
      </View>

      {/* What happens next */}
      {req.status !== 'cancelled' && req.status !== 'completed' && (
        <View style={[styles.section, { backgroundColor: C.cream2, borderColor: C.line }]}>
          <Text style={styles.sectionH}>What happens next</Text>
          <Text style={styles.nextTxt}>
            {req.status === 'requested'
              ? "We've received your request and will be in touch soon to discuss your needs."
              : req.status === 'contacted'
                ? "We've reached out to you. If you haven't heard from us, give us a call."
                : req.status === 'quoted'
                  ? "We've sent you a quote. Reply to confirm or give us a call to discuss."
                  : "Your request is in progress. We'll keep you posted."}
          </Text>
        </View>
      )}

      {/* Actions */}
      <View style={styles.actions}>
        <Pressable style={styles.btnOutline} onPress={load} disabled={loading}>
          <MaterialCommunityIcons name="refresh" size={18} color={C.green} />
          <Text style={styles.btnOutlineTxt}>Refresh status</Text>
        </Pressable>

        <Pressable
          style={styles.btnPhone}
          onPress={() => void Linking.openURL(`tel:${PHONE}`)}
          accessibilityLabel={`Call ${PHONE}`}
        >
          <MaterialCommunityIcons name="phone" size={18} color="#fff" />
          <Text style={styles.btnTxt}>Call us</Text>
        </Pressable>

        {canCancel && (
          <Pressable
            style={[styles.btnDanger, cancelling && { opacity: 0.5 }]}
            onPress={handleCancel}
            disabled={cancelling}
          >
            <Text style={styles.btnDangerTxt}>
              {cancelling ? 'Cancelling…' : 'Cancel this request'}
            </Text>
          </Pressable>
        )}

        <Pressable onPress={() => router.push('/(tabs)/menu')}>
          <Text style={styles.linkTxt}>Browse services</Text>
        </Pressable>
      </View>
    </ScrollView>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.detailRow}>
      <Text style={styles.detailLbl}>{label}</Text>
      <Text style={styles.detailVal}>{value}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  center: {
    flex: 1, backgroundColor: C.cream, alignItems: 'center',
    justifyContent: 'center', padding: 30, gap: 16,
  },
  errTxt: { color: C.burg, fontSize: 15, textAlign: 'center' },
  banner: {
    borderRadius: 16, padding: 18, flexDirection: 'row',
    alignItems: 'center', gap: 14, marginBottom: 16,
  },
  bannerTitle: { color: '#fff', fontWeight: '800', fontSize: 16 },
  bannerSub: { color: 'rgba(255,255,255,0.85)', fontSize: 13, marginTop: 3 },
  quoteCard: {
    backgroundColor: C.green, borderRadius: 14, padding: 20,
    alignItems: 'center', marginBottom: 16, gap: 4,
  },
  quoteLabel: { color: 'rgba(255,255,255,0.8)', fontSize: 13, fontWeight: '600', letterSpacing: 1 },
  quoteAmount: { color: '#fff', fontSize: 36, fontWeight: '800' },
  quoteNote: { color: 'rgba(255,255,255,0.85)', fontSize: 14, textAlign: 'center', marginTop: 4 },
  section: {
    backgroundColor: '#fff', borderRadius: 14, padding: 18, marginBottom: 14,
    borderWidth: 1, borderColor: C.line,
  },
  sectionH: { fontWeight: '800', fontSize: 15, color: C.green, marginBottom: 12 },
  detailRow: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 7, borderBottomWidth: 1, borderBottomColor: C.line, gap: 10,
  },
  detailLbl: { color: C.mut, fontSize: 14, flexShrink: 0 },
  detailVal: { color: C.ink, fontSize: 14, flex: 1, textAlign: 'right' },
  nextTxt: { color: C.mut, fontSize: 14, lineHeight: 20 },
  actions: { gap: 12, marginTop: 4 },
  btn: {
    backgroundColor: C.green, borderRadius: 999,
    paddingVertical: 14, alignItems: 'center',
  },
  btnTxt: { color: '#fff', fontWeight: '700', fontSize: 15 },
  btnOutline: {
    borderWidth: 2, borderColor: C.green, borderRadius: 999, paddingVertical: 13,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  btnOutlineTxt: { color: C.green, fontWeight: '700', fontSize: 15 },
  btnPhone: {
    backgroundColor: C.green, borderRadius: 999, paddingVertical: 14,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
  },
  btnDanger: {
    borderWidth: 2, borderColor: C.burg, borderRadius: 999,
    paddingVertical: 13, alignItems: 'center',
  },
  btnDangerTxt: { color: C.burg, fontWeight: '700', fontSize: 15 },
  linkTxt: {
    color: C.green, fontWeight: '600', fontSize: 14, textAlign: 'center',
    textDecorationLine: 'underline',
  },
})
