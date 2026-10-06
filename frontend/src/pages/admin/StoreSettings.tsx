import { useEffect, useState } from 'react'
import { adminGetStoreSettings, adminPutStoreSettings, naira } from '../../api'
import type { StoreInfo } from '../../api'

export function AdminStoreSettings() {
  const [store, setStore] = useState<StoreInfo | null>(null)
  const [form, setForm] = useState({ delivery_fee_minor: '', order_cutoff_time: '', max_advance_days: '' })
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    adminGetStoreSettings()
      .then(s => {
        setStore(s)
        setForm({
          delivery_fee_minor: String(s.delivery_fee_minor / 100),
          order_cutoff_time: s.order_cutoff_time,
          max_advance_days: String(s.max_advance_days),
        })
      })
      .catch(() => setErr('Store settings are not configured yet.'))
      .finally(() => setLoading(false))
  }, [])

  const set = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement>) => setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    const fee = Math.round(Number(form.delivery_fee_minor) * 100)
    const days = Number(form.max_advance_days)
    if (isNaN(fee) || fee < 0) return setErr('Enter a valid delivery fee.')
    if (!/^\d{2}:\d{2}$/.test(form.order_cutoff_time)) return setErr('Cutoff must be HH:MM.')
    if (isNaN(days) || days < 0) return setErr('Enter a valid advance days number.')
    setBusy(true)
    setErr('')
    setSaved(false)
    try {
      const updated = await adminPutStoreSettings({
        delivery_fee_minor: fee,
        order_cutoff_time: form.order_cutoff_time,
        max_advance_days: days,
      })
      setStore(updated)
      setSaved(true)
    } catch {
      setErr('Could not save store settings.')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="adm-section"><p className="note">Loading…</p></div>

  return (
    <div className="adm-section">
      <div className="adm-section-hdr"><h1>Store settings</h1></div>
      {store && (
        <div className="adm-info-row">
          <span>Currency <b>{store.currency}</b></span>
          <span>Timezone <b>{store.timezone}</b></span>
          {store && <span>Current delivery fee <b>{naira(store.delivery_fee_minor)}</b></span>}
        </div>
      )}
      <div className="adm-form" style={{ maxWidth: 480 }}>
        <label className="fld">Delivery fee (₦)
          <input className="inp" type="number" min={0} value={form.delivery_fee_minor} onChange={set('delivery_fee_minor')} />
        </label>
        <label className="fld">Order cutoff time (HH:MM, business timezone)
          <input className="inp" type="text" placeholder="16:00" value={form.order_cutoff_time} onChange={set('order_cutoff_time')} />
        </label>
        <label className="fld">Max advance days
          <input className="inp" type="number" min={0} value={form.max_advance_days} onChange={set('max_advance_days')} />
        </label>
        {err && <p className="err">{err}</p>}
        {saved && <p className="adm-ok">Settings saved.</p>}
        <div className="adm-actions">
          <button className="btn" onClick={() => void submit()} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
        </div>
      </div>
    </div>
  )
}
