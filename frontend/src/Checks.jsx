import React, { useState } from 'react'
import { write } from './api'
import { JalaliField, MoneyField } from './FinanceFields'
import { persianDate, tehranToday } from './dates'
import RecordActions from './RecordActions'
import './checks.css'

const toman = value => `${new Intl.NumberFormat('fa-IR').format(value || 0)} تومان`

export default function Checks({ data, refresh }) {
  const [direction, setDirection] = useState('incoming')
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const accounts = data.accounts.filter(a => a.active)
  const set = (key, value) => setForm(old => ({ ...old, [key]: value }))
  const openCreate = () => { setError(''); setForm({ mode: 'create', direction, sender_name: '', receiver_name: '', counterparty_account: '', account: '', category: '', amount: '', due_date: tehranToday(), notes: '' }) }
  const openEdit = check => { setError(''); setForm({ mode: 'edit', check, direction: check.direction, sender_name: check.sender_name,
    receiver_name: check.receiver_name, counterparty_account: check.counterparty_account || '',
    account: check.direction === 'incoming' ? check.receiver_account : check.sender_account, category: check.category,
    amount: String(check.amount), due_date: check.due_date, notes: check.notes || '' }) }
  const openClear = check => { setError(''); setForm({ mode: 'clear', check, amount: String(check.remaining_amount), date: tehranToday(), idempotency_key: crypto.randomUUID() }) }
  const openClearingEdit = (check, clearing) => { setError(''); setForm({ mode: 'clearing-edit', check, clearing, amount: String(clearing.amount), date: clearing.date, idempotency_key: crypto.randomUUID() }) }
  async function save(event) {
    event.preventDefault()
    if (saving) return
    setSaving(true); setError('')
    try {
      if (form.mode === 'create' || form.mode === 'edit') {
        const incoming = form.direction === 'incoming'
        await write(form.mode === 'edit' ? `checks/${form.check.id}/` : 'checks/', { direction: form.direction, sender_name: incoming ? form.sender_name.trim() : form.mode === 'edit' ? form.sender_name.trim() : accounts.find(a => a.id === Number(form.account))?.name || '',
          receiver_name: incoming ? form.mode === 'edit' ? form.receiver_name.trim() : accounts.find(a => a.id === Number(form.account))?.name || '' : form.receiver_name.trim(),
          sender_account: incoming ? null : Number(form.account), receiver_account: incoming ? Number(form.account) : null,
          counterparty_account: form.counterparty_account.trim(), category: Number(form.category), amount: Number(form.amount), due_date: form.due_date, notes: form.notes }, form.mode === 'edit' ? 'PATCH' : 'POST')
      } else {
        await write(form.mode === 'clearing-edit' ? `checks/${form.check.id}/clearings/${form.clearing.id}/` : `checks/${form.check.id}/clear/`,
          { amount: Number(form.amount), date: form.date, idempotency_key: form.idempotency_key }, form.mode === 'clearing-edit' ? 'PATCH' : 'POST')
      }
      setForm(null); await refresh()
    } catch (e) { setError(e.message) } finally { setSaving(false) }
  }
  const items = data.checks.filter(check => check.direction === direction)
  return <section className="checks-page">
    <div className="section-title"><h2>چک‌ها</h2><button onClick={openCreate}>افزودن چک</button></div>
    <p className="page-intro">چک تا زمان تسویه روی موجودی و گزارش درآمد یا هزینه اثر ندارد.</p>
    <div className="obligation-tabs" role="tablist" aria-label="نوع چک">{[['incoming','چک‌های دریافتی'],['outgoing','چک‌های پرداختی']].map(([key,label]) =>
      <button key={key} role="tab" aria-selected={direction === key} className={direction === key ? 'active' : ''} onClick={() => setDirection(key)}>{label}</button>)}</div>
    <div className="check-list">{items.length ? items.map(check => <article className="check-card" key={check.id}>
      <div className="check-head"><strong>{check.sender_name} ← {check.receiver_name}</strong><span className={`obligation-status ${check.status === 'cleared' ? 'settled' : check.status}`}>{check.status === 'cleared' ? 'تسویه‌شده' : check.status === 'partial' ? 'بخشی تسویه‌شده' : check.is_overdue ? 'سررسیدگذشته' : 'در انتظار'}</span></div>
      <p>سررسید: {persianDate(check.due_date)} · {check.category_name}{check.counterparty_account ? ` · حساب طرف مقابل: ${check.counterparty_account}` : ''}</p>
      <div className="check-amounts"><span>مبلغ: <b>{toman(check.amount)}</b></span><span>مانده: <b>{toman(check.remaining_amount)}</b></span></div>
      {check.notes && <p>{check.notes}</p>}
      {check.clearings.length > 0 && <details><summary>سوابق تسویه ({check.clearings.length})</summary>{check.clearings.map(row => <div key={row.id}><p>{persianDate(row.date)} · {toman(row.amount)}</p><RecordActions label={`تسویه ${row.amount} تومانی`} path={`checks/${check.id}/clearings/${row.id}/`} onEdit={() => openClearingEdit(check, row)} refresh={refresh} warning="اثر این تسویه از موجودی و گزارش‌ها برگردانده می‌شود."/></div>)}</details>}
      {check.remaining_amount > 0 && <button className="obligation-pay" onClick={() => openClear(check)}>ثبت تسویه</button>}
      <RecordActions label={`${check.sender_name} ← ${check.receiver_name}`} path={`checks/${check.id}/`} onEdit={() => openEdit(check)} refresh={refresh}/>
    </article>) : <div className="empty">چکی در این بخش ثبت نشده است.</div>}</div>
    {form && <div className="overlay" onClick={() => setForm(null)}><div className="sheet" onClick={event => event.stopPropagation()}>
      <div className="sheet-head"><h2>{form.mode === 'create' ? 'ثبت چک' : form.mode === 'edit' ? 'ویرایش چک' : form.mode === 'clearing-edit' ? 'ویرایش تسویه' : 'ثبت تسویه چک'}</h2><button type="button" onClick={() => setForm(null)} aria-label="بستن">×</button></div>
      <form onSubmit={save}>{['create','edit'].includes(form.mode) ? <>
        <div className="tabs">{[['incoming','دریافتی'],['outgoing','پرداختی']].map(([key,label]) => <button type="button" key={key} disabled={form.mode === 'edit' && form.check.cleared_amount > 0} className={form.direction === key ? 'active' : ''} onClick={() => set('direction', key)}>{label}</button>)}</div>
        {form.direction === 'incoming' && <label>فرستنده چک<input required maxLength={120} value={form.sender_name} onChange={e => set('sender_name', e.target.value)}/></label>}
        <label>{form.direction === 'incoming' ? 'حساب گیرنده (ما)' : 'حساب فرستنده (ما)'}<select required disabled={form.mode === 'edit' && form.check.cleared_amount > 0} value={form.account} onChange={e => set('account', e.target.value)}><option value="">انتخاب کنید</option>{accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        {form.direction === 'outgoing' && <label>گیرنده چک<input required maxLength={120} value={form.receiver_name} onChange={e => set('receiver_name', e.target.value)}/></label>}
        <label>حساب طرف مقابل (اختیاری)<input maxLength={120} value={form.counterparty_account} onChange={e => set('counterparty_account', e.target.value)}/></label>
        <MoneyField label="مبلغ چک (تومان)" value={form.amount} onChange={value => set('amount', value)}/>
        <JalaliField label="تاریخ سررسید چک" value={form.due_date} onChange={value => set('due_date', value)}/>
        <label>دسته<select required disabled={form.mode === 'edit' && form.check.cleared_amount > 0} value={form.category} onChange={e => set('category', e.target.value)}><option value="">انتخاب کنید</option>{data.categories.filter(c => c.type === (form.direction === 'incoming' ? 'income' : 'expense')).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
        <label>یادداشت<input value={form.notes} onChange={e => set('notes', e.target.value)}/></label>
      </> : <><p>مانده: {toman(form.check.remaining_amount)}</p><MoneyField label="مبلغ تسویه (تومان)" value={form.amount} onChange={value => set('amount', value)}/><JalaliField label="تاریخ تسویه" value={form.date} onChange={value => set('date', value)}/></>}
      {error && <div className="error" role="alert">{error}</div>}<button className="primary" disabled={saving}>{saving ? 'در حال ذخیره…' : ['edit','clearing-edit'].includes(form.mode) ? 'ذخیره تغییرات' : 'ثبت و ذخیره'}</button></form>
    </div></div>}
  </section>
}
