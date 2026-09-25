import React from 'react'
import DatePicker from 'react-multi-date-picker'
import persian from 'react-date-object/calendars/persian'
import persian_fa from 'react-date-object/locales/persian_fa'
import { gregorianDateFromPicker } from './dates'
import { amountInPersianWords, formatAmountInput, normalizeDigits } from './money'

export function JalaliField({ label, value, onChange, required = true }) {
  return <label>{label}<DatePicker value={value ? new Date(`${value}T12:00:00`) : null} calendar={persian} locale={persian_fa}
    format="YYYY/MM/DD" calendarPosition="bottom-right" inputClass="jalali-date-input" required={required}
    onChange={selected => onChange(selected ? gregorianDateFromPicker(selected) : '')}/></label>
}

export function MoneyField({ label, value, onChange }) {
  return <label className="money-input-field">{label}<input inputMode="numeric" required value={formatAmountInput(value)}
    onChange={event => onChange(normalizeDigits(event.target.value).replace(/[^0-9]/g, ''))}/>
    <small className="amount-in-words" aria-live="polite">{amountInPersianWords(value) || 'مبلغ به حروف'}</small></label>
}
