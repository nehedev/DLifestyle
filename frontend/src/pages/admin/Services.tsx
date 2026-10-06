import { useCallback, useEffect, useState } from 'react'
import { adminCreateService, adminListServices, adminPatchService } from '../../api'
import type { ServiceAdmin, ServiceCreate } from '../../api'

const EMPTY: ServiceCreate = { name: '', description: '', is_active: true, sort_order: null }

function ServiceForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: ServiceCreate & { id?: number }
  onSave: (s: ServiceAdmin) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const set = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm(f => ({ ...f, [k]: e.target.value }))

  const submit = async () => {
    if (!form.name.trim()) return setErr('Name is required.')
    if (!form.description.trim()) return setErr('Description is required.')
    setBusy(true)
    setErr('')
    try {
      const payload: ServiceCreate = {
        name: form.name.trim(),
        description: form.description.trim(),
        is_active: form.is_active,
        sort_order: form.sort_order !== null && form.sort_order !== undefined
          ? Number(form.sort_order) : null,
      }
      const saved = form.id
        ? await adminPatchService(form.id, payload)
        : await adminCreateService(payload)
      onSave(saved)
    } catch {
      setErr('Could not save service.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="adm-overlay" onClick={onCancel}>
      <aside className="adm-drawer" onClick={e => e.stopPropagation()}>
        <div className="adm-drawer-hdr">
          <h2>{form.id ? 'Edit service' : 'New service'}</h2>
          <button className="adm-close" onClick={onCancel} aria-label="Close"><iconify-icon icon="lucide:x" /></button>
        </div>
        <div className="adm-form">
          <label className="fld">Name<input className="inp" value={form.name} onChange={set('name')} /></label>
          <label className="fld">Description
            <textarea className="inp" rows={3} value={form.description} onChange={set('description')} />
          </label>
          <label className="fld">Sort order (leave blank for auto)
            <input className="inp" type="number" value={form.sort_order ?? ''} onChange={set('sort_order')} />
          </label>
          <div className="adm-toggles">
            <label>
              <input type="checkbox" checked={form.is_active ?? true}
                onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} />
              {' '}Active
            </label>
          </div>
          {err && <p className="err">{err}</p>}
          <div className="adm-actions">
            <button className="btn" onClick={() => void submit()} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
            <button className="btn ghost" onClick={onCancel}>Cancel</button>
          </div>
        </div>
      </aside>
    </div>
  )
}

export function AdminServices() {
  const [items, setItems] = useState<ServiceAdmin[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [editing, setEditing] = useState<(ServiceCreate & { id?: number }) | null>(null)

  const load = useCallback(async (cur: string | null, append: boolean) => {
    setLoading(true)
    try {
      const page = await adminListServices(cur)
      setItems(prev => append ? [...prev, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setHasMore(page.next_cursor !== null)
    } catch {
      setErr('Could not load services.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(null, false) }, [load])

  const handleSaved = (s: ServiceAdmin) => {
    setItems(prev => {
      const idx = prev.findIndex(i => i.id === s.id)
      return idx >= 0 ? prev.map(i => i.id === s.id ? s : i) : [s, ...prev]
    })
    setEditing(null)
  }

  const openEdit = (s: ServiceAdmin) =>
    setEditing({ id: s.id, name: s.name, description: s.description, is_active: s.is_active, sort_order: s.sort_order })

  return (
    <div className="adm-section">
      <div className="adm-section-hdr">
        <h1>Services</h1>
        <button className="btn sm" onClick={() => setEditing(EMPTY)}>+ New service</button>
      </div>
      {err && <p className="err">{err}</p>}
      <table className="adm-table">
        <thead>
          <tr><th>Name</th><th>Sort</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          {items.map(s => (
            <tr key={s.id} className={s.is_active ? '' : 'adm-inactive'}>
              <td>{s.name}</td>
              <td>{s.sort_order}</td>
              <td>{s.is_active ? '✓' : '—'}</td>
              <td><button className="btn sm" onClick={() => openEdit(s)}>Edit</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !loading && <p className="note">No services yet.</p>}
      {hasMore && (
        <button className="btn ghost sm" disabled={loading} onClick={() => void load(cursor, true)}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
      {editing && <ServiceForm initial={editing} onSave={handleSaved} onCancel={() => setEditing(null)} />}
    </div>
  )
}
