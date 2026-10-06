import { MaterialCommunityIcons } from '@expo/vector-icons'
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
  type KeyboardTypeOptions,
} from 'react-native'
import { C } from '../../theme'
import type { ReactNode } from 'react'

// ─── Badge ──────────────────────────────────────────────────────────────────

export function Badge({ status }: { status: string }) {
  const s = status.toLowerCase()
  let bg = C.mut
  if (s.includes('cancel') || s.includes('fail')) bg = C.burg
  else if (s.includes('complete') || s.includes('paid') || s.includes('ready')) bg = C.green
  else if (s.includes('preparing') || s.includes('pending') || s.includes('processing')) bg = '#B8791F'
  else if (s.includes('active') || s.includes('success')) bg = C.green
  else if (s.includes('inactive') || s.includes('sold')) bg = C.burg
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      <Text style={styles.badgeTxt}>{status}</Text>
    </View>
  )
}

// ─── Field ──────────────────────────────────────────────────────────────────

export function Field({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  multiline,
  hint,
}: {
  label: string
  value: string
  onChangeText: (v: string) => void
  placeholder?: string
  keyboardType?: KeyboardTypeOptions
  multiline?: boolean
  hint?: string
}) {
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={styles.fldLabel}>{label}</Text>
      <TextInput
        style={[styles.input, multiline && { height: 90, textAlignVertical: 'top' }]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={C.mut}
        keyboardType={keyboardType}
        multiline={multiline}
      />
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  )
}

// ─── Button ─────────────────────────────────────────────────────────────────

export function Btn({
  title,
  onPress,
  variant = 'primary',
  busy,
  disabled,
}: {
  title: string
  onPress: () => void
  variant?: 'primary' | 'ghost' | 'danger'
  busy?: boolean
  disabled?: boolean
}) {
  const bg = variant === 'primary' ? C.green : variant === 'danger' ? C.burg : 'transparent'
  const color = variant === 'ghost' ? C.green : '#fff'
  const border = variant === 'ghost' ? C.green : bg
  return (
    <Pressable
      style={[
        styles.btn,
        { backgroundColor: bg, borderColor: border },
        (disabled || busy) && { opacity: 0.5 },
      ]}
      onPress={onPress}
      disabled={disabled || busy}
    >
      {busy ? (
        <ActivityIndicator color={color} />
      ) : (
        <Text style={[styles.btnTxt, { color }]}>{title}</Text>
      )}
    </Pressable>
  )
}

// ─── Drawer ─────────────────────────────────────────────────────────────────

export function Drawer({
  visible,
  onClose,
  title,
  children,
}: {
  visible: boolean
  onClose: () => void
  title: string
  children: ReactNode
}) {
  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.drawerBackdrop}>
        <View style={styles.drawer}>
          <View style={styles.drawerHdr}>
            <Text style={styles.drawerTitle}>{title}</Text>
            <Pressable onPress={onClose} hitSlop={10}>
              <MaterialCommunityIcons name="close" size={24} color={C.mut} />
            </Pressable>
          </View>
          <ScrollView
            contentContainerStyle={{ padding: 20 }}
            keyboardShouldPersistTaps="handled"
          >
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  )
}

// ─── List scaffolding ───────────────────────────────────────────────────────

export function ListEmpty({ loading, text }: { loading: boolean; text: string }) {
  if (loading) return <ActivityIndicator color={C.green} style={{ marginTop: 40 }} />
  return <Text style={styles.empty}>{text}</Text>
}

export function AdminScreenShell({
  title,
  action,
  children,
  onBack,
}: {
  title: string
  action?: ReactNode
  children: ReactNode
  onBack: () => void
}) {
  return (
    <View style={{ flex: 1, backgroundColor: '#f4f6f5' }}>
      <View style={styles.topbar}>
        <Pressable onPress={onBack} hitSlop={10} style={styles.backBtn}>
          <MaterialCommunityIcons name="chevron-left" size={26} color="#fff" />
        </Pressable>
        <Text style={styles.topbarTitle}>{title}</Text>
        <View style={{ minWidth: 26 }}>{action}</View>
      </View>
      {children}
    </View>
  )
}

// ─── Weekday picker ─────────────────────────────────────────────────────────
// Backend uses ISO weekdays: 1=Monday … 7=Sunday

const DAYS: { label: string; iso: number }[] = [
  { label: 'Mon', iso: 1 },
  { label: 'Tue', iso: 2 },
  { label: 'Wed', iso: 3 },
  { label: 'Thu', iso: 4 },
  { label: 'Fri', iso: 5 },
  { label: 'Sat', iso: 6 },
  { label: 'Sun', iso: 7 },
]

export function WeekdayPicker({
  value,
  onChange,
}: {
  value: number[]
  onChange: (days: number[]) => void
}) {
  return (
    <View style={{ marginBottom: 14 }}>
      <Text style={styles.fldLabel}>Available days</Text>
      <View style={styles.weekdays}>
        {DAYS.map(({ label, iso }) => {
          const on = value.includes(iso)
          return (
            <Pressable
              key={iso}
              style={[styles.day, on && styles.dayOn]}
              onPress={() =>
                onChange(on ? value.filter((x) => x !== iso) : [...value, iso].sort((a, b) => a - b))
              }
            >
              <Text style={[styles.dayTxt, on && styles.dayTxtOn]}>{label}</Text>
            </Pressable>
          )
        })}
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  badge: { paddingHorizontal: 10, paddingVertical: 3, borderRadius: 999, alignSelf: 'flex-start' },
  badgeTxt: { color: '#fff', fontWeight: '700', fontSize: 12 },
  fldLabel: { fontWeight: '600', fontSize: 13, marginBottom: 6, color: C.ink },
  input: {
    borderWidth: 1.5, borderColor: '#C9C58F', borderRadius: 10,
    paddingHorizontal: 14, paddingVertical: 11, backgroundColor: '#fff',
    fontSize: 15, color: C.ink,
  },
  hint: { color: C.mut, fontSize: 12, marginTop: 4 },
  btn: {
    borderWidth: 2, borderRadius: 999, paddingVertical: 12,
    alignItems: 'center', justifyContent: 'center', minHeight: 44,
  },
  btnTxt: { fontWeight: '700', fontSize: 15 },
  drawerBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.45)', flexDirection: 'row', justifyContent: 'flex-end' },
  drawer: { width: '100%', maxWidth: 520, backgroundColor: '#fff', height: '100%' },
  drawerHdr: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: 20, paddingVertical: 16,
    borderBottomWidth: 1, borderBottomColor: C.line,
  },
  drawerTitle: { fontSize: 18, fontWeight: '800', color: C.green },
  empty: { textAlign: 'center', color: C.mut, paddingVertical: 40 },
  topbar: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 12, paddingVertical: 14, backgroundColor: C.greenDark,
    gap: 8,
  },
  backBtn: { padding: 4 },
  topbarTitle: { flex: 1, color: '#fff', fontWeight: '800', fontSize: 17 },
  weekdays: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  day: {
    paddingHorizontal: 12, paddingVertical: 7, borderRadius: 999,
    borderWidth: 1.5, borderColor: C.line,
  },
  dayOn: { backgroundColor: C.green, borderColor: C.green },
  dayTxt: { fontWeight: '600', fontSize: 13, color: C.mut },
  dayTxtOn: { color: '#fff' },
})