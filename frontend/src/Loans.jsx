import React, { useState } from 'react'
import { Plus, ArrowDownRight, ArrowUpLeft } from 'lucide-react'
import { write } from './api'
import { persianDate, tehranToday } from './dates'
import { JalaliField, MoneyField } from './FinanceFields'
import './loans.css'

const toman = amount => `${new Intl.NumberFormat('fa-IR').format(Number(amount || 0))} تومان`

export default function Loans({ data, refresh }) {
  const [direction, setDirection] = useState('borrowed')
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const accounts = data.accounts.filter(account => account.active)
  const loans = data.loans.filter(loan => loan.direction === direction)
  const set = (key, value) => setForm(old => ({ ...old, [key]: value }))

  function openCreate() {
    setError('')
    setForm({ mode: 'create', direction, party: '', principal: '', start_date: tehranToday(),
      rate: '', schedule: false, count: '', first_due_date: tehranToday(), maturity_date: '',
      account: '', notes: '' })
  }

  function openRepayment(loan) {
    setError('')
    setForm({ mode: 'repay', loan, amount: String(loan.remaining_balance), date: tehranToday(),
      account: loan.origination_account || '', idempotency_key: crypto.randomUUID() })
  }

  async function save(event) {
    event.preventDefault()
    if (saving) return
    setSaving(true)
    setError('')
    try {
      if (form.mode === 'create') {
        await write('loans/', { direction: form.direction, party: form.party.trim(), original_principal: form.principal,
          start_date: form.start_date, annual_interest_rate: form.rate === '' ? null : form.rate,
          maturity_date: form.schedule ? null : form.maturity_date || null,
          installment_count: form.schedule ? Number(form.count) : undefined,
          first_due_date: form.schedule ? form.first_due_date : undefined,
          origination_account: form.account ? Number(form.account) : null, notes: form.notes })
      } else {
        await write(`loans/${form.loan.id}/repay/`, { amount: form.amount, date: form.date,
          account: Number(form.account), idempotency_key: form.idempotency_key })
      }
      setForm(null)
      await refresh()
    } catch (exception) { setError(exception.message) }
    finally { setSaving(false) }
  }

  return <>
    <div className="page-intro">اصل وام و سود آن جدا از هم ثبت می‌شوند.</div>
    <div className="obligation-tabs" role="tablist" aria-label="جهت وام">
      {[['borrowed','وام گرفته‌شده'],['lent','وام داده‌شده']].map(([id,label]) =>
        <button key={id} role="tab" aria-selected={direction === id} className={direction === id ? 'active' : ''}
          onClick={() => setDirection(id)}>{label}</button>)}
    </div>
    <div className="section-title"><h2>{direction === 'borrowed' ? 'وام‌های گرفته‌شده' : 'وام‌های داده‌شده'}</h2>
      <button onClick={openCreate}><Plus size={17}/> افزودن وام</button></div>
    <div className="loan-list">{loans.length ? loans.map(loan => <article className="loan-card" key={loan.id}>
      <div className="loan-head"><div className="obligation-icon">{direction === 'borrowed' ? <ArrowDownRight/> : <ArrowUpLeft/>}</div>
        <div><h3>{loan.party}</h3><small>شروع {persianDate(loan.start_date)}{loan.maturity_date ? ` · پایان ${persianDate(loan.maturity_date)}` : ''}</small></div>
        <span className={`obligation-status ${loan.remaining_balance ? 'partial' : 'settled'}`}>{loan.remaining_balance ? 'باز' : 'تسویه شده'}</span></div>
      <div className="loan-amounts"><div><small>اصل اولیه</small><strong>{toman(loan.original_principal)}</strong></div>
        <div><small>اصل باقی‌مانده</small><strong>{toman(loan.remaining_principal)}</strong></div>
        <div><small>سود باقی‌مانده</small><strong>{toman(loan.remaining_interest)}</strong></div>
        <div><small>مانده کل</small><strong>{toman(loan.remaining_balance)}</strong></div></div>
      <p className="loan-terms">{loan.annual_interest_rate === null ? 'بدون نرخ سود ثبت‌شده' : `سود ساده سالانه ${loan.annual_interest_rate}٪ · کل سود ثابت دوره ${toman(loan.total_interest)}`}
        {loan.origination_account_name ? ` · اصل وام در حساب ${loan.origination_account_name} ثبت شد` : ' · جابه‌جایی اصل اولیه در حساب ثبت نشده است'}</p>
      {loan.notes && <p className="obligation-detail">{loan.notes}</p>}
      {loan.installments.length > 0 && <details className="obligation-history" open={loan.installments.some(item => item.status === 'overdue')}>
        <summary>اقساط ماهانه ({loan.installments.length})</summary>
        {loan.installments.map(item => <div className="loan-installment" key={item.id}><span>{persianDate(item.due_date)}</span>
          <span>{toman(item.remaining_amount)} مانده</span><b className={item.status}>{item.status === 'overdue' ? 'سررسید گذشته' : item.status === 'settled' ? 'تسویه شده' : 'در پیش'}</b></div>)}</details>}
      {loan.repayments.length > 0 && <details className="obligation-history"><summary>سوابق بازپرداخت ({loan.repayments.length})</summary>
        {loan.repayments.map(payment => <div key={payment.id}>{persianDate(payment.date)} · {toman(payment.amount)}
          <small>اصل {toman(payment.principal_amount)} · سود {toman(payment.interest_amount)} · {payment.account_name}</small></div>)}</details>}
      {loan.remaining_balance > 0 && <button className="obligation-pay" onClick={() => openRepayment(loan)}>
        {direction === 'borrowed' ? 'ثبت بازپرداخت' : 'ثبت دریافت قسط'}</button>}
    </article>) : <div className="empty">هنوز وامی در این بخش ثبت نشده است.</div>}</div>

    {form && <div className="overlay" onClick={() => setForm(null)}><div className="sheet" onClick={event => event.stopPropagation()}>
      <div className="sheet-head"><h2>{form.mode === 'create' ? 'ثبت وام' : `بازپرداخت وام ${form.loan.party}`}</h2>
        <button type="button" onClick={() => setForm(null)} aria-label="بستن">×</button></div>
      <form onSubmit={save}>{form.mode === 'create' ? <>
        <label>نوع وام<select value={form.direction} onChange={event => set('direction', event.target.value)}>
          <option value="borrowed">گرفته‌شده</option><option value="lent">داده‌شده</option></select></label>
        <label>{form.direction === 'borrowed' ? 'وام‌دهنده' : 'وام‌گیرنده'}<input required maxLength={120} value={form.party}
          onChange={event => set('party', event.target.value)}/></label>
        <MoneyField label="اصل وام (تومان)" value={form.principal} onChange={value => set('principal', value)}/>
        <JalaliField label="تاریخ شروع" value={form.start_date} onChange={value => set('start_date', value)}/>
        <label>حساب جابه‌جایی اصل وام (اختیاری)<select value={form.account} onChange={event => set('account', event.target.value)}>
          <option value="">وام قبلی؛ بدون ثبت جابه‌جایی وجه</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
        <p className="hint">اگر اصل وام اکنون دریافت یا پرداخت شده، حساب را انتخاب کنید. برای وام قبلی که در موجودی حساب لحاظ شده، خالی بگذارید.</p>
        <label>نرخ سود سالانه (٪، اختیاری)<input type="number" inputMode="decimal" min="0" max="100" step="0.01"
          value={form.rate} onChange={event => set('rate', event.target.value)} placeholder="بدون سود"/></label>
        <label className="loan-check"><input type="checkbox" checked={form.schedule} onChange={event => set('schedule', event.target.checked)}/> اقساط مساوی ماهانه</label>
        {form.schedule ? <><label>تعداد اقساط<input type="number" min="1" max="120" required value={form.count}
          onChange={event => set('count', event.target.value)}/></label>
          <JalaliField label="تاریخ اولین قسط" value={form.first_due_date} onChange={value => set('first_due_date', value)}/></>
          : form.rate !== '' && Number(form.rate) > 0 && <JalaliField label="تاریخ پایان محاسبه سود" value={form.maturity_date}
              onChange={value => set('maturity_date', value)}/>}
        <p className="hint">سود ساده برای کل دوره محاسبه و ثابت می‌شود؛ بهره مرکب و جریمه دیرکرد محاسبه نمی‌شود. هنگام بازپرداخت، ابتدا سود و سپس اصل تسویه می‌شود.</p>
        <label>یادداشت (اختیاری)<textarea value={form.notes} onChange={event => set('notes', event.target.value)}/></label>
      </> : <>
        <p className="obligation-form-summary">مانده اصل: {toman(form.loan.remaining_principal)} · مانده سود: {toman(form.loan.remaining_interest)}</p>
        <MoneyField label="مبلغ این بازپرداخت (تومان)" value={form.amount} onChange={value => set('amount', value)}/>
        <JalaliField label="تاریخ پرداخت" value={form.date} onChange={value => set('date', value)}/>
        <label>{form.loan.direction === 'borrowed' ? 'پرداخت از حساب' : 'دریافت در حساب'}<select required value={form.account}
          onChange={event => set('account', event.target.value)}><option value="">انتخاب کنید</option>
          {accounts.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
        <p className="hint">بخش سود در درآمد یا هزینه ثبت می‌شود. بازپرداخت اصل وام فقط موجودی حساب و مانده وام را تغییر می‌دهد.</p>
      </>}
        {error && <div className="error" role="alert">{error}</div>}
        <button className="primary" disabled={saving}>{saving ? 'در حال ثبت…' : 'ثبت و ذخیره'}</button>
      </form></div></div>}
  </>
}
