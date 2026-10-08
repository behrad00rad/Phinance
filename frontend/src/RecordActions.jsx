import React, { useState } from 'react'
import { Pencil, Trash2 } from 'lucide-react'
import { write } from './api'
import './record-actions.css'

export default function RecordActions({ label, path, onEdit, refresh, deleteLabel = 'حذف', warning = 'پرداخت‌های وابسته نیز حذف می‌شوند و اثرشان از موجودی و گزارش‌ها برمی‌گردد.' }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function remove() {
    if (!window.confirm(`${deleteLabel} «${label}»؟\n${warning}`)) return
    setBusy(true)
    setError('')
    try { await write(path, {}, 'DELETE'); await refresh() }
    catch (exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  return <><div className="record-actions"><button type="button" onClick={onEdit} disabled={busy}><Pencil size={15}/> ویرایش</button><button type="button" className="record-delete" onClick={remove} disabled={busy}><Trash2 size={15}/> {busy ? 'در حال حذف…' : deleteLabel}</button></div>{error && <div className="record-error" role="alert">{error}</div>}</>
}
