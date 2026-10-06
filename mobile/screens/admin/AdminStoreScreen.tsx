import { useCallback, useEffect, useState } from 'react'
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, View } from 'react-native'
import { useNavigation } from '@react-navigation/native'
import { adminGetStoreSettings, adminPutStoreSettings } from '../../api'
import { AdminScreenShell, Btn, Field } from './ui'
import { C } from '../../theme'

export default function AdminStoreScreen() {
  const nav = useNavigation()
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [fee, setFee] = useState('')
  const [cutoff, setCutoff] = useState('')
  const [maxDays, setMaxDays] = useState('')
  const [currency, setCurrency] = useState('')
  const [timezone, setTimezone] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await adminGetStoreSettings()
      setFee((s.delivery_fee_minor / 100).toFixed(2))
      setCutoff(s.order_cutoff_time)
      setMaxDays(String(s.max_advance_days))
      setCurrency(s.currency)
      setTimezone(s.timezone)
    } catch (e) {
      Alert.alert('Could not load', e instanceof Error ? e.message : 'Unknown error')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { void load() }, [load])

  const save = async () => {
    const feeMinor = Math.round(Number(fee) * 100)
    const days = Number(maxDays)
    if (!Number.isFinite(feeMinor) || feeMinor < 0 || !Number.isFinite(days) || days < 0) {
      Alert.alert('Invalid input', 'Check the fee and max advance days.')
      return
    }
    setBusy(true)
    try {
      await adminPutStoreSettings({
        delivery_fee_minor: feeMinor,
        order_cutoff_time: cutoff,
        max_advance_days: days,
      })
      Alert.alert('Saved', 'Store settings updated.')
    } catch (e) {
      Alert.alert('Save failed', e instanceof Error ? e.message : 'Unknown error')
    } finally { setBusy(false) }
  }

  return (
    <AdminScreenShell title="Store settings" onBack={() => nav.goBack()}>
      {loading ? (
        <ActivityIndicator color={C.green} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView contentContainerStyle={{ padding: 20, paddingBottom: 60 }} keyboardShouldPersistTaps="handled">
          <Field label="Delivery fee (₦)" value={fee} onChangeText={setFee} keyboardType="decimal-pad" />
          <Field label="Order cutoff time" value={cutoff} onChangeText={setCutoff} hint="24-hour clock, e.g. 18:00" />
          <Field label="Max advance days" value={maxDays} onChangeText={setMaxDays} keyboardType="number-pad" />

          <View style={styles.readonly}>
            <Text style={styles.roLbl}>Currency</Text>
            <Text style={styles.roVal}>{currency}</Text>
          </View>
          <View style={styles.readonly}>
            <Text style={styles.roLbl}>Timezone</Text>
            <Text style={styles.roVal}>{timezone}</Text>
          </View>

          <View style={{ marginTop: 16 }}>
            <Btn title="Save settings" onPress={save} busy={busy} />
          </View>
        </ScrollView>
      )}
    </AdminScreenShell>
  )
}

const styles = StyleSheet.create({
  readonly: {
    flexDirection: 'row', justifyContent: 'space-between',
    paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.line,
  },
  roLbl: { fontWeight: '600', color: C.mut },
  roVal: { fontWeight: '600', color: C.ink },
})