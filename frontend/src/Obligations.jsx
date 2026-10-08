import React, { useState } from 'react'
import { Plus, ArrowDownRight, ArrowUpLeft, CalendarDays, ChevronLeft } from 'lucide-react'
import { write } from './api'
import { persianDate, tehranToday } from './dates'
import { JalaliField, MoneyField } from './FinanceFields'
import RecordActions from './RecordActions'
import Loans from './Loans'
import './obligations.css'

const sections = [
  { kind: 'expected_payment', label: 'دریافتی‌ها', singular: 'دریافتی مورد انتظار', party: 'پرداخت‌کننده', incoming: true },
  { kind: 'bill', label: 'قبوض', singular: 'قبض', party: 'دریافت‌کننده', incoming: false },
  { kind: 'debt_owed', label: 'بدهی ما', singular: 'بدهی خانواده', party: 'طلبکار', incoming: false },
  { kind: 'debt_receivable', label: 'طلب‌های ما', singular: 'طلب خانواده', party: 'بدهکار', incoming: true },
]

const toman = amount => `${new Intl.NumberFormat('fa-IR').format(Number(amount || 0))} تومان`

function statusLabel(item, section) {
  if (item.status === 'settled') return section.incoming ? 'دریافت شده' : 'تسویه شده'
  if (item.status === 'partial') return section.incoming ? 'بخشی دریافت شده' : 'بخشی پرداخت شده'
  return section.incoming ? 'در انتظار دریافت' : 'در پیش'
}

export default function Obligations({ data, refresh, showChecks }) {
  const [kind, setKind] = useState('expected_payment')
  const [filter, setFilter] = useState('open')
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [showLoans, setShowLoans] = useState(false)
  const section = sections.find(item => item.kind === kind)
  const accounts = data.accounts.filter(account => account.active)
  const items = data.obligations.filter(item => item.kind === kind && (
    filter === 'all' || (filter === 'overdue' ? item.is_overdue : filter === 'upcoming' ? !item.is_overdue && item.status !== 'settled' : filter === 'open' ? item.status !== 'settled' : item.status === 'settled')
  ))
  const set = (key, value) => setForm(old => ({ ...old, [key]: value }))

  function openCreate() {
    setError('')
    setForm({ mode: 'create', kind, counterparty: '', amount: '', due_date: tehranToday(),
      destination_account: '', category: '', notes: '' })
  }

  function openEdit(item) {
    setError('')
    setForm({ mode: 'edit', item, kind: item.kind, counterparty: item.counterparty, amount: String(item.amount),
      due_date: item.due_date, destination_account: item.destination_account || '', category: item.category || '', notes: item.notes || '' })
  }

  function openSettlement(item) {
    setError('')
    setForm({ mode: 'settle', item, amount: String(item.remaining_amount), date: tehranToday(),
      account: item.destination_account || '', idempotency_key: crypto.randomUUID() })
  }
  function openSettlementEdit(item, payment) {
    setError('')
    setForm({ mode: 'settlement-edit', item, payment, amount: String(payment.amount), date: payment.date,
      account: payment.account, idempotency_key: crypto.randomUUID() })
  }

  async function save(event) {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setError('')
    try {
      if (form.mode === 'create' || form.mode === 'edit') {
        await write(form.mode === 'edit' ? `obligations/${form.item.id}/` : 'obligations/', { kind: form.kind, counterparty: form.counterparty.trim(), amount: Number(form.amount),
          due_date: form.due_date, destination_account: form.kind === 'expected_payment' ? Number(form.destination_account) : null,
          category: ['expected_payment', 'bill'].includes(form.kind) ? Number(form.category) : null, notes: form.notes }, form.mode === 'edit' ? 'PATCH' : 'POST')
      } else {
        await write(form.mode === 'settlement-edit' ? `obligations/${form.item.id}/settlements/${form.payment.id}/` : `obligations/${form.item.id}/settle/`,
          { amount: Number(form.amount), date: form.date, account: Number(form.account), idempotency_key: form.idempotency_key },
          form.mode === 'settlement-edit' ? 'PATCH' : 'POST')
      }
      setForm(null)
      await refresh()
    } catch (exception) { setError(exception.message) }
    finally { setSaving(false) }
  }

  if (showLoans) return <><button className="back-link" onClick={() => setShowLoans(false)}>بازگشت به سررسیدها</button><Loans data={data} refresh={refresh}/></>

  return <>
    <div className="dues-shortcuts"><button className="loan-entry" onClick={() => setShowLoans(true)}>وام‌ها <ChevronLeft size={17}/></button>
    <button className="loan-entry" onClick={showChecks}>چک‌ها <ChevronLeft size={17}/></button></div>
    <div className="obligation-tabs" role="tablist" aria-label="نوع سررسید">
      {sections.map(item => <button key={item.kind} role="tab" aria-selected={kind === item.kind}
        className={kind === item.kind ? 'active' : ''} onClick={() => { setKind(item.kind); setFilter('open') }}>{item.label}</button>)}
    </div>
    <div className="section-title"><h2>{section.label}</h2><button onClick={openCreate}><Plus size={17}/> افزودن</button></div>
    <div className="obligation-filters" aria-label="وضعیت">
      {[['open','باز'],['upcoming','در پیش'],['overdue','دیرکرد'],['settled','تسویه شده']].map(([id,label]) =>
        <button key={id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>{label}</button>)}
    </div>
    <div className="obligation-list">{items.length ? items.map(item => <article className="obligation-card" key={item.id}>
      <div className="obligation-card-head"><div className="obligation-icon">{section.incoming ? <ArrowDownRight size={23}/> : <ArrowUpLeft size={23}/>}</div>
        <div><h3>{item.counterparty}</h3><small>{section.party} · {section.singular}</small></div>
        <span className={`obligation-status ${item.status}`}>{statusLabel(item, section)}</span></div>
      <div className="obligation-meta"><span><CalendarDays size={16}/> سررسید: {persianDate(item.due_date)}</span>
        {item.is_overdue && <strong className="obligation-overdue">سررسید گذشته</strong>}</div>
      <div className="obligation-amounts"><div><small>مبلغ کل</small><strong>{toman(item.amount)}</strong></div>
        <div><small>{section.incoming ? 'دریافت شده' : 'پرداخت شده'}</small><strong>{toman(item.settled_amount)}</strong></div>
        <div><small>باقی‌مانده</small><strong>{toman(item.remaining_amount)}</strong></div></div>
      {(item.destination_account_name || item.category_name) && <p className="obligation-detail">{[item.destination_account_name, item.category_name].filter(Boolean).join(' · ')}</p>}
      {item.notes && <p className="obligation-detail">{item.notes}</p>}
      {item.settlements.length > 0 && <details className="obligation-history"><summary>سوابق {section.incoming ? 'دریافت' : 'پرداخت'} ({item.settlements.length})</summary>
        {item.settlements.map(payment => <div key={payment.id}>{persianDate(payment.date)} · {toman(payment.amount)} · {payment.account_name}<RecordActions label={`پرداخت ${payment.amount} تومانی`} path={`obligations/${item.id}/settlements/${payment.id}/`} onEdit={() => openSettlementEdit(item, payment)} refresh={refresh} warning="اثر این پرداخت از موجودی و گزارش‌ها برگردانده می‌شود."/></div>)}</details>}
      {item.remaining_amount > 0 && <button className="obligation-pay" onClick={() => openSettlement(item)}>{section.incoming ? 'ثبت دریافت' : 'ثبت پرداخت'}</button>}
      <RecordActions label={item.counterparty} path={`obligations/${item.id}/`} onEdit={() => openEdit(item)} refresh={refresh}/>
    </article>) : <div className="empty">موردی برای نمایش وجود ندارد.</div>}</div>
    {form && <div className="overlay" onClick={() => setForm(null)}><div className="sheet" onClick={event => event.stopPropagation()}>
      <div className="sheet-head"><h2>{form.mode === 'create' ? `افزودن ${sections.find(item => item.kind === form.kind).singular}` : form.mode === 'edit' ? `ویرایش ${form.item.counterparty}` : form.mode === 'settlement-edit' ? 'ویرایش پرداخت' : `${section.incoming ? 'ثبت دریافت از' : 'ثبت پرداخت به'} ${form.item.counterparty}`}</h2>
        <button type="button" onClick={() => setForm(null)} aria-label="بستن">×</button></div>
      <form onSubmit={save}>
        {['create', 'edit'].includes(form.mode) ? <>
          <label>{sections.find(item => item.kind === form.kind).party}<input required maxLength={120} value={form.counterparty} onChange={event => set('counterparty', event.target.value)}/></label>
          <MoneyField label="مبلغ کل (تومان)" value={form.amount} onChange={value => set('amount', value)}/>
          <JalaliField label={form.kind === 'bill' || form.kind === 'debt_owed' ? 'تاریخ سررسید' : 'تاریخ دریافت مورد انتظار'} value={form.due_date} onChange={value => set('due_date', value)}/>
          {form.kind === 'expected_payment' && <label>حساب مقصد<select required value={form.destination_account} onChange={event => set('destination_account', event.target.value)}>
            <option value="">انتخاب کنید</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>}
          {['expected_payment','bill'].includes(form.kind) && <label>دسته<select required value={form.category} onChange={event => set('category', event.target.value)}>
            <option value="">انتخاب کنید</option>{data.categories.filter(category => category.type === (form.kind === 'bill' ? 'expense' : 'income'))
              .map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>}
          <label>یادداشت (اختیاری)<textarea value={form.notes} onChange={event => set('notes', event.target.value)}/></label>
          {form.mode === 'edit' && form.item.settled_amount > 0 && <p className="hint">پس از ثبت پرداخت، حساب و دسته ثابت می‌مانند. مبلغ کل باید از مبلغ پرداخت‌شده کمتر نباشد.</p>}
        </> : <>
          <p className="obligation-form-summary">باقی‌مانده: <strong>{toman(form.item.remaining_amount)}</strong></p>
          <MoneyField label="مبلغ این مرحله (تومان)" value={form.amount} onChange={value => set('amount', value)}/>
          <JalaliField label="تاریخ ثبت" value={form.date} onChange={value => set('date', value)}/>
          <label>{section.incoming ? 'واریز به حساب' : 'پرداخت از حساب'}<select required value={form.account} onChange={event => set('account', event.target.value)}>
            <option value="">انتخاب کنید</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
        </>}
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={saving}>{saving ? 'در حال ذخیره…' : ['edit','settlement-edit'].includes(form.mode) ? 'ذخیره تغییرات' : 'ثبت و ذخیره'}</button>
      </form>
    </div></div>}
  </>
}
