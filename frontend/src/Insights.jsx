import React, { useEffect, useState } from 'react'
import { api } from './api'
import { persianDate } from './dates'
import { JalaliField } from './FinanceFields'
import './insights.css'

const toman = value => `${new Intl.NumberFormat('fa-IR').format(Number(value || 0))} تومان`

function NetWorthChart({ points }) {
  if (!points.length || points.every(point => point.value === 0)) return <div className="empty">هنوز داده‌ای برای برآورد خالص دارایی وجود ندارد.</div>
  const values = points.map(point => point.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const spread = max - min || 1
  const positions = points.map((point, index) => ({ x: points.length === 1 ? 300 : 35 + index * 530 / (points.length - 1),
    y: 145 - (point.value - min) * 110 / spread }))
  const path = positions.map((point, index) => `${index ? 'L' : 'M'} ${point.x} ${point.y}`).join(' ')
  return <><svg className="insights-line-chart" viewBox="0 0 600 180" role="img" aria-label="روند برآورد خالص دارایی">
    <line x1="35" y1="145" x2="565" y2="145" className="chart-axis"/>
    <path d={path} className="chart-line"/>
    {positions.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="5" className="chart-point"/>)}
  </svg><div className="insights-history-labels">{points.map((point, index) => <div key={index}><small>{point.label}</small><strong>{toman(point.value)}</strong></div>)}</div></>
}

export default function Insights({ back }) {
  const [report, setReport] = useState(null)
  const [range, setRange] = useState({ start: '', end: '' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(nextRange) {
    setLoading(true)
    setError('')
    try {
      const query = nextRange?.start && nextRange?.end ? `?start=${nextRange.start}&end=${nextRange.end}` : ''
      const result = await api(`insights/${query}`)
      setReport(result)
      setRange({ start: result.start, end: result.end })
    } catch (exception) { setError(exception.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])
  const maxMonthly = Math.max(1, ...(report?.monthly || []).flatMap(row => [row.income, row.expense]))
  const maxCategory = Math.max(1, ...(report?.expense_categories || []).flatMap(row => [row.amount, row.previous_amount]))
  const hasCashFlow = report?.monthly.some(row => row.income || row.expense)

  return <>
    <button className="back-link" onClick={back}>بازگشت به بیشتر</button>
    <div className="page-intro">روند پول واقعی و سررسیدهای پیش رو</div>
    <section className="insights-panel"><h2>بازه گزارش</h2><div className="insights-range">
      {range.start && <JalaliField label="از تاریخ" value={range.start} onChange={value => setRange(old => ({ ...old, start: value }))}/>}
      {range.end && <JalaliField label="تا تاریخ" value={range.end} onChange={value => setRange(old => ({ ...old, end: value }))}/>}
      <button className="primary" disabled={loading || !range.start || !range.end} onClick={() => load(range)}>نمایش گزارش</button>
    </div>{report && <p className="insights-caption">{persianDate(report.start)} تا {persianDate(report.end)} · همه مبلغ‌ها به تومان</p>}</section>
    {error && <div className="error" role="alert">{error}</div>}
    {loading && !report && <div className="empty">در حال آماده‌سازی گزارش…</div>}
    {report && <>
      <div className="insights-totals"><div><small>درآمد واقعی</small><strong className="positive">{toman(report.totals.income)}</strong></div>
        <div><small>هزینه واقعی</small><strong className="negative">{toman(report.totals.expense)}</strong></div>
        <div><small>خالص جریان پول</small><strong>{toman(report.totals.net)}</strong></div></div>
      <section className="insights-panel"><h2>دخل‌وخرج ماهانه</h2><p className="insights-caption">ماه‌های شمسی در بازه انتخاب‌شده؛ فقط تراکنش‌های ثبت‌شده</p>
        {!hasCashFlow ? <div className="empty">در این بازه درآمد یا هزینه‌ای ثبت نشده است.</div> :
          <div className="insights-monthly">{report.monthly.map(row => <div className="insights-month" key={`${row.year}-${row.month}`}>
            <div className="insights-month-head"><strong>{row.label}</strong><span>خالص {toman(row.net)}</span></div>
            <div className="insights-bar-line"><span>درآمد</span><div className="insights-track"><div className="insights-bar income" style={{ width: `${row.income / maxMonthly * 100}%` }}/></div><b>{toman(row.income)}</b></div>
            <div className="insights-bar-line"><span>هزینه</span><div className="insights-track"><div className="insights-bar expense" style={{ width: `${row.expense / maxMonthly * 100}%` }}/></div><b>{toman(row.expense)}</b></div>
          </div>)}</div>}
      </section>
      <section className="insights-panel"><h2>هزینه‌ها بر اساس دسته</h2>
        <p className="insights-caption">مقایسه با دوره قبلیِ هم‌طول: {persianDate(report.previous_start)} تا {persianDate(report.previous_end)}</p>
        {!report.expense_categories.length ? <div className="empty">هزینه‌ای در این دوره یا دوره قبلی ثبت نشده است.</div> :
          <div className="insights-categories">{report.expense_categories.map(row => <div className="insights-category" key={row.category_id ?? row.name}>
            <div><strong>{row.name}</strong><span>{toman(row.amount)} · {row.change >= 0 ? 'افزایش' : 'کاهش'} {toman(Math.abs(row.change))}</span></div>
            <div className="insights-track"><div className="insights-bar expense" style={{ width: `${row.amount / maxCategory * 100}%` }}/></div>
            <div className="insights-track"><div className="insights-bar previous" style={{ width: `${row.previous_amount / maxCategory * 100}%` }}/></div>
            <small>دوره قبلی: {toman(row.previous_amount)}</small></div>)}</div>}
      </section>
      <section className="insights-panel"><h2>سررسیدها</h2><p className="insights-caption">مبلغ‌های برنامه‌ریزی‌شده جدا از جریان پول واقعی؛ پیش رو تا {report.due.next_days} روز آینده</p>
        <div className="insights-due-grid">{[['bill','قبوض'],['expected_payment','دریافتی‌های مورد انتظار']].map(([kind,label]) => {
          const row = report.due.totals[kind]
          return <div key={kind}><strong>{label}</strong><small>در پیش: {row.upcoming_count} مورد · {toman(row.upcoming_amount)}</small>
            <small className="negative">سررسید گذشته: {row.overdue_count} مورد · {toman(row.overdue_amount)}</small></div>
        })}</div>
        {report.due.items.length > 0 && <div className="insights-due-list">{report.due.items.map(item => <div key={item.id}>
          <span>{item.counterparty} · {persianDate(item.due_date)}</span><b>{toman(item.remaining_amount)}</b></div>)}</div>}
      </section>
      <section className="insights-panel"><h2>مانده وام‌ها</h2><div className="insights-due-grid">
        {[["borrowed","وام‌های گرفته‌شده"],["lent","وام‌های داده‌شده"]].map(([direction,label]) => {
          const row = report.loans[direction]
          return <div key={direction}><strong>{label} · {row.count} مورد</strong><small>اصل: {toman(row.principal)}</small>
            <small>سود: {toman(row.interest)}</small><b>کل مانده: {toman(row.total)}</b></div>
        })}</div></section>
      <section className="insights-panel"><h2>روند برآورد خالص دارایی</h2>
        <p className="insights-caption">مانده حساب‌ها، اصل طلب و بدهی، دارایی‌ها و طلا در پایان هر ماه شمسی. ارزش فعلی دارایی و قیمت فعلی طلا برای ماه‌های گذشته نیز استفاده شده است؛ این نمودار ارزش تاریخی دقیق نیست.</p>
        <NetWorthChart points={report.net_worth_history}/></section>
    </>}
  </>
}
