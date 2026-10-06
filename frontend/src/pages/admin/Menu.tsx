import { useCallback, useEffect, useState } from 'react'
import {
  adminCreateMenuItem,
  adminListMenuItems,
  adminPatchMenuItem,
  adminSignUpload,
  naira,
} from '../../api'
import type { MenuItemAdmin, MenuItemCreate } from '../../api'

const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function WeekdayPicker({
  value,
  onChange,
}: {
  value: number[]
  onChange: (days: number[]) => void
}) {
  const toggle = (d: number) =>
    onChange(value.includes(d) ? value.filter(x => x !== d) : [...value, d].sort((a, b) => a - b))
  return (
    <div className="adm-weekdays">
      {WEEKDAY_LABELS.map((label, i) => {
        const day = i + 1
        return (
          <label key={day} className={`adm-day${value.includes(day) ? ' on' : ''}`}>
            <input
              type="checkbox"
              checked={value.includes(day)}
              onChange={() => toggle(day)}
              className="sr"
            />
            {label}
          </label>
        )
      })}
    </div>
  )
}

const EMPTY_FORM: MenuItemCreate = {
  name: '', description: '', category: '', image_url: '', image_alt: '',
  price_minor: 0, weekdays: [], is_active: true, is_sold_out: false,
}

function MenuItemForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: MenuItemCreate & { id?: number }
  onSave: (item: MenuItemAdmin) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState(initial)
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState('')

  const set = (k: keyof typeof form) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm(f => ({ ...f, [k]: e.target.value }))

  const uploadImage = async (file: File) => {
    setUploading(true)
    setErr('')
    try {
      const sign = await adminSignUpload()
      const fd = new FormData()
      fd.append('file', file)
      fd.append('api_key', sign.api_key)
      fd.append('timestamp', String(sign.timestamp))
      fd.append('folder', sign.folder)
      fd.append('signature', sign.signature)
      const res = await fetch(sign.upload_url, { method: 'POST', body: fd })
      const data = await res.json() as { secure_url?: string; original_filename?: string }
      if (!data.secure_url) throw new Error('Upload failed')
      setForm(f => ({
        ...f,
        image_url: data.secure_url!,
        image_alt: f.image_alt || data.original_filename || '',
      }))
    } catch {
      setErr('Image upload failed. Check your Cloudinary settings.')
    } finally {
      setUploading(false)
    }
  }

  const submit = async () => {
    if (!form.name.trim()) return setErr('Name is required.')
    if (!form.category.trim()) return setErr('Category is required.')
    if (!form.weekdays.length) return setErr('Select at least one day.')
    setBusy(true)
    setErr('')
    try {
      const payload: MenuItemCreate = {
        ...form,
        name: form.name.trim(),
        description: form.description?.trim() || null,
        category: form.category.trim(),
        image_url: form.image_url?.trim() || null,
        image_alt: form.image_alt?.trim() || null,
        price_minor: Number(form.price_minor),
      }
      const saved = form.id
        ? await adminPatchMenuItem(form.id, payload)
        : await adminCreateMenuItem(payload)
      onSave(saved)
    } catch {
      setErr('Could not save menu item.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="adm-overlay" onClick={onCancel}>
      <aside className="adm-drawer" onClick={e => e.stopPropagation()}>
        <div className="adm-drawer-hdr">
          <h2>{form.id ? 'Edit item' : 'New item'}</h2>
          <button className="adm-close" onClick={onCancel} aria-label="Close"><iconify-icon icon="lucide:x" /></button>
        </div>
        <div className="adm-form">
          <label className="fld">Name<input className="inp" value={form.name} onChange={set('name')} /></label>
          <label className="fld">Category
            <input className="inp" value={form.category} onChange={set('category')} placeholder="Rice, Beans, Pasta…" />
          </label>
          <label className="fld">Price (kobo)
            <input className="inp" type="number" min={0} value={form.price_minor} onChange={set('price_minor')} />
          </label>
          <label className="fld">Description
            <textarea className="inp" rows={2} value={form.description ?? ''} onChange={set('description')} />
          </label>
          <label className="fld">Image URL
            <input className="inp" value={form.image_url ?? ''} onChange={set('image_url')} placeholder="https://…" />
          </label>
          <label className="fld">Or upload image
            <input
              type="file"
              accept="image/*"
              className="inp"
              onChange={e => { if (e.target.files?.[0]) void uploadImage(e.target.files[0]) }}
              disabled={uploading}
            />
          </label>
          {form.image_url && <img src={form.image_url} alt="" className="adm-thumb" />}
          <label className="fld">Image alt text
            <input className="inp" value={form.image_alt ?? ''} onChange={set('image_alt')} />
          </label>
          <div className="fld">Days served<WeekdayPicker value={form.weekdays} onChange={days => setForm(f => ({ ...f, weekdays: days }))} /></div>
          <div className="adm-toggles">
            <label><input type="checkbox" checked={form.is_active} onChange={e => setForm(f => ({ ...f, is_active: e.target.checked }))} /> Active</label>
            <label><input type="checkbox" checked={form.is_sold_out} onChange={e => setForm(f => ({ ...f, is_sold_out: e.target.checked }))} /> Sold out</label>
          </div>
          {err && <p className="err">{err}</p>}
          <div className="adm-actions">
            <button className="btn" onClick={() => void submit()} disabled={busy || uploading}>{busy ? 'Saving…' : 'Save'}</button>
            <button className="btn ghost" onClick={onCancel}>Cancel</button>
          </div>
        </div>
      </aside>
    </div>
  )
}

export function AdminMenu() {
  const [items, setItems] = useState<MenuItemAdmin[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const [editing, setEditing] = useState<(MenuItemCreate & { id?: number }) | null>(null)

  const load = useCallback(async (cur: string | null, append: boolean) => {
    setLoading(true)
    try {
      const page = await adminListMenuItems(cur)
      setItems(prev => append ? [...prev, ...page.items] : page.items)
      setCursor(page.next_cursor)
      setHasMore(page.next_cursor !== null)
    } catch {
      setErr('Could not load menu items.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load(null, false) }, [load])

  const handleSaved = (item: MenuItemAdmin) => {
    setItems(prev => {
      const idx = prev.findIndex(i => i.id === item.id)
      return idx >= 0 ? prev.map(i => i.id === item.id ? item : i) : [item, ...prev]
    })
    setEditing(null)
  }

  const openEdit = (item: MenuItemAdmin) =>
    setEditing({
      id: item.id, name: item.name, description: item.description,
      category: item.category, image_url: item.image_url, image_alt: item.image_alt,
      price_minor: item.price_minor, weekdays: item.weekdays,
      is_active: item.is_active, is_sold_out: item.is_sold_out,
    })

  return (
    <div className="adm-section">
      <div className="adm-section-hdr">
        <h1>Menu items</h1>
        <button className="btn sm" onClick={() => setEditing(EMPTY_FORM)}>+ New item</button>
      </div>
      {err && <p className="err">{err}</p>}
      <table className="adm-table">
        <thead>
          <tr><th>Name</th><th>Category</th><th>Price</th><th>Days</th><th>Active</th><th>Sold out</th><th></th></tr>
        </thead>
        <tbody>
          {items.map(item => (
            <tr key={item.id} className={item.is_active ? '' : 'adm-inactive'}>
              <td>
                {item.image_url && <img src={item.image_url} alt="" className="adm-row-thumb" />}
                {item.name}
              </td>
              <td>{item.category}</td>
              <td>{naira(item.price_minor)}</td>
              <td>{item.weekdays.map(d => WEEKDAY_LABELS[d - 1]).join(', ')}</td>
              <td>{item.is_active ? '✓' : '—'}</td>
              <td>{item.is_sold_out ? '✓' : '—'}</td>
              <td><button className="btn sm" onClick={() => openEdit(item)}>Edit</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !loading && <p className="note">No menu items yet.</p>}
      {hasMore && (
        <button className="btn ghost sm" disabled={loading} onClick={() => void load(cursor, true)}>
          {loading ? 'Loading…' : 'Load more'}
        </button>
      )}
      {editing && (
        <MenuItemForm initial={editing} onSave={handleSaved} onCancel={() => setEditing(null)} />
      )}
    </div>
  )
}
