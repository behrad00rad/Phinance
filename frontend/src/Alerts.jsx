import React, { useEffect, useState } from 'react'
import { api, write } from './api'
import './alerts.css'

const labels = { bills: 'قبوض', loans: 'اقساط وام', expected_income: 'دریافتی‌های عقب‌افتاده', high_spending: 'هزینه غیرعادی دسته‌ها' }
const dateLabel = value => value ? new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium' }).format(new Date(value + 'T12:00:00')) : ''

export default function Alerts({ back, onChanged }) {
  const [items, setItems] = useState([])
  const [preferences, setPreferences] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function refresh() {
    try {
      const [history, settings] = await Promise.all([api('notifications/'), api('alert-preferences/')])
      setItems(history.items); setPreferences(settings); setError('')
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { refresh() }, [])
  async function change(field, value) {
    setBusy(true)
    try {
      const next = await write('alert-preferences/', { [field]: value }, 'PATCH')
      setPreferences(next); await refresh()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  async function markRead(id) {
    try { await write(`notifications/${id}/read/`, {}); setItems(old => old.map(item => item.id === id ? { ...item, read: true } : item)); onChanged() }
    catch (e) { setError(e.message) }
  }
  return <div className="alerts-page">
    <button className="back-link" onClick={back}>بازگشت به بیشتر</button>
    <p className="page-intro">یادآوری‌ها هنگام باز کردن این صفحه بررسی می‌شوند. تاریخچه هشدارها برای شما ذخیره می‌شود.</p>
    {error && <div className="error" role="alert">{error}</div>}
    <section className="preference-card"><h2>تنظیمات هشدار</h2>
      {preferences && <><div className="alert-switches">{Object.entries(labels).map(([key, label]) =>
        <label key={key}><span>{label}</span><input type="checkbox" checked={preferences[key]} disabled={busy} onChange={e => change(key, e.target.checked)}/></label>)}</div>
        <label className="alert-days">چند روز پیش از سررسید قبوض و اقساط؟ <select value={preferences.days_ahead} disabled={busy} onChange={e => change('days_ahead', Number(e.target.value))}>{[0,1,3,7,14,30,60,90].map(days => <option key={days} value={days}>{new Intl.NumberFormat('fa-IR').format(days)} روز</option>)}</select></label>
        <small>دریافتی مورد انتظار فقط پس از گذشت تاریخ آن هشدار می‌دهد. هزینه غیرعادی با دوره مشابه ماه قبل مقایسه می‌شود.</small></>}
    </section>
    <div className="section-title"><h2>تاریخچه اعلان‌ها</h2><span>{new Intl.NumberFormat('fa-IR').format(items.filter(item => !item.read).length)} خوانده‌نشده</span></div>
    {items.length ? <div className="alert-history">{items.map(item => <article key={item.id} className={'alert-item ' + (item.read ? '' : 'unread')}>
      <div><strong>{item.title}</strong><p>{item.detail}</p><small>{item.due_date ? `سررسید: ${dateLabel(item.due_date)} · ` : ''}ثبت: {new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.created_at))}</small></div>
      {!item.read && <button onClick={() => markRead(item.id)}>خواندم</button>}
    </article>)}</div> : <div className="empty">هنوز هشداری ثبت نشده است.</div>}
  </div>
}
