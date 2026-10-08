import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import DateObject from 'react-date-object'
import persian from 'react-date-object/calendars/persian'
import { persianDate, tehranToday } from './dates'
import { amountInPersianWords, formatAmountInput, normalizeDigits } from './money'
import './calendar.css'
import './calendar-extra.css'

const digits = value => new Intl.NumberFormat('fa-IR', { useGrouping: false }).format(value)
const isoDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
const dateObject = value => new DateObject({ date: new Date(`${value}T12:00:00`), calendar: persian })
const monthNames = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند']

export function JalaliField({ label, value, onChange, required = true }) {
  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => {
    const day = dateObject(value || tehranToday())
    return { year: day.year, month: day.month.number }
  })
  useEffect(() => {
    if (!open) return undefined
    const closeOnEscape = event => { if (event.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [open])
  const selected = value || ''
  const today = tehranToday()
  const currentJalaliYear = dateObject(today).year
  const years = Array.from({ length: 201 }, (_, index) => currentJalaliYear - 100 + index)
  function show() {
    const day = dateObject(value || today)
    setView({ year: day.year, month: day.month.number })
    setOpen(true)
  }
  function move(delta) {
    const index = view.year * 12 + view.month - 1 + delta
    setView({ year: Math.floor(index / 12), month: ((index % 12) + 12) % 12 + 1 })
  }
  function select(date) { onChange(isoDate(date)); setOpen(false) }
  const first = new DateObject({ calendar: persian, year: view.year, month: view.month, day: 1 }).toDate()
  const offset = (first.getDay() + 1) % 7
  const monthLength = new DateObject({ calendar: persian, year: view.year, month: view.month, day: 1 }).month.length
  const cells = Array.from({ length: 42 }, (_, index) => {
    const day = index - offset + 1
    if (day < 1 || day > monthLength) return null
    const date = new DateObject({ calendar: persian, year: view.year, month: view.month, day }).toDate()
    return { day, date, iso: isoDate(date) }
  })
  return <div className="jalali-field"><span className="jalali-label">{label}{required ? '' : ' (اختیاری)'}</span>
    <button type="button" className="jalali-trigger" onClick={show} aria-label={`${label}: ${value ? persianDate(value) : 'انتخاب تاریخ'}`}>
      <span>{value ? persianDate(value) : 'انتخاب تاریخ'}</span><span aria-hidden="true">▦</span>
    </button>
    {open && createPortal(<div className="jalali-overlay" onClick={() => setOpen(false)}>
      <div className="jalali-dialog" role="dialog" aria-modal="true" aria-label={`انتخاب تاریخ برای ${label}`} onClick={event => event.stopPropagation()}>
        <div className="jalali-dialog-head"><strong>انتخاب تاریخ</strong><button type="button" onClick={() => setOpen(false)} aria-label="بستن تقویم">×</button></div>
        <div className="jalali-month-bar"><button type="button" onClick={() => move(-1)} aria-label="ماه قبل">→</button>
          <div className="jalali-pickers"><select aria-label="ماه شمسی" value={view.month} onChange={event => setView(old => ({ ...old, month: Number(event.target.value) }))}>{monthNames.map((month, index) => <option key={month} value={index + 1}>{month}</option>)}</select><select aria-label="سال شمسی" value={view.year} onChange={event => setView(old => ({ ...old, year: Number(event.target.value) }))}>{years.map(year => <option key={year} value={year}>{digits(year)}</option>)}</select></div>
          <button type="button" onClick={() => move(1)} aria-label="ماه بعد">←</button>
          <button type="button" className="jalali-today" onClick={() => select(new Date(`${today}T12:00:00`))}>امروز</button></div>
        <div className="jalali-grid" role="grid" aria-label={`${monthNames[view.month - 1]} ${digits(view.year)}`}>
          {['ش','ی','د','س','چ','پ','ج'].map((day, index) => <span className="jalali-weekday" key={index}>{day}</span>)}
          {cells.map((cell, index) => cell ? <button type="button" key={cell.iso} className={`${cell.iso === selected ? 'selected' : ''} ${cell.iso === today ? 'today' : ''}`}
            aria-label={persianDate(cell.iso)} aria-pressed={cell.iso === selected} onClick={() => select(cell.date)}>{digits(cell.day)}</button>
            : <span key={`empty-${index}`} className="jalali-empty"/>)}
        </div>
      </div>
    </div>, document.body)}
  </div>
}

export function MoneyField({ label, value, onChange }) {
  return <label className="money-input-field">{label}<input inputMode="numeric" required value={formatAmountInput(value)}
    onChange={event => onChange(normalizeDigits(event.target.value).replace(/[^0-9]/g, ''))}/>
    <small className="amount-in-words" aria-live="polite">{amountInPersianWords(value) || 'مبلغ به حروف'}</small></label>
}
