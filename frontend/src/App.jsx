import React, { useEffect, useState } from 'react'
import { Home, ArrowLeftRight, Wallet, Shapes, MoreHorizontal, Plus, ArrowUpLeft, ArrowDownRight, ChevronLeft, LogOut, UserRound, Sun, Moon, Settings, CalendarDays, Bell, Eye, EyeOff, TrendingUp } from 'lucide-react'
import { api, write } from './api'
import { tehranToday } from './dates'
import { amountInPersianWords, formatAmountInput, normalizeDigits } from './money'
import Obligations from './Obligations'
import Insights from './Insights'
import Alerts from './Alerts'
import Checks from './Checks'
import { JalaliField } from './FinanceFields'
import RecordActions from './RecordActions'

const money = value => new Intl.NumberFormat('fa-IR').format(Number(value || 0)) + ' تومان'
const number = value => new Intl.NumberFormat('fa-IR').format(Number(value || 0))
const today = tehranToday
const nav = [{ id: 'home', label: 'خانه', icon: Home }, { id: 'transactions', label: 'تراکنش‌ها', icon: ArrowLeftRight }, { id: 'dues', label: 'سررسیدها', icon: CalendarDays }, { id: 'assets', label: 'دارایی‌ها', icon: Shapes }, { id: 'more', label: 'بیشتر', icon: MoreHorizontal }]
const pageTitles = { home: 'خانه', transactions: 'تراکنش‌ها', dues: 'سررسیدها', assets: 'دارایی‌ها', more: 'بیشتر', profile: 'پروفایل', insights: 'گزارش‌ها', alerts: 'اعلان‌ها', checks: 'چک‌ها' }

function App() {
  const [user, setUser] = useState(null), [page, setPage] = useState('home'), [data, setData] = useState(null)
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [form, setForm] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('phinance-theme') || 'light')
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('phinance-theme', theme) }, [theme])
  async function refresh() {
    try {
      const [dashboard, accounts, categories, transactions, assets, gold, purchases, sales, obligations, loans, checks, notifications] = await Promise.all([
        api('dashboard/'), api('accounts/'), api('categories/'), api('transactions/'), api('assets/'), api('gold/summary/'), api('gold-purchases/'), api('gold-sales/'), api('obligations/'), api('loans/'), api('checks/'), api('notifications/')])
      setData({ dashboard, accounts, categories, transactions, assets, gold, purchases, sales, obligations, loans, checks, notifications })
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { (async () => { try { await api('auth/csrf/'); setUser(await api('auth/me/')); await refresh() } catch {} finally { setLoading(false) } })() }, [])
  async function submit(path, payload, method = 'POST') { try { setError(''); await write(path, payload, method); setForm(null); await refresh() } catch (e) { setError(e.message) } }
  if (loading) return <div className="center">در حال بارگذاری…</div>
  if (!user) return <Login onSuccess={async u => { setUser(u); await refresh() }} />
  return <div className="app"><header className="top"><div className="top-heading"><div className="eyebrow">Phinance · مدیریت آسان پول</div><h1>{pageTitles[page]}</h1></div><div className="top-actions"><button className="header-alert" onClick={() => setPage('alerts')} aria-label="اعلان‌ها"><Bell size={20}/>{data?.notifications?.unread_count > 0 && <span>{new Intl.NumberFormat('fa-IR').format(data.notifications.unread_count)}</span>}</button><button className="avatar" onClick={() => setPage('profile')} aria-label="پروفایل">{user.username.slice(0, 1).toUpperCase()}</button></div></header>
    <main>
      {error && <div className="error" role="alert">{error}<button onClick={() => setError('')}>×</button></div>}
      {!data ? <p>در حال بارگذاری…</p> : <>
        {page === 'home' && <HomePage data={data} navigate={setPage} open={kind => setForm({ kind })} />}
        {page === 'transactions' && <Transactions data={data} open={(kind, item) => setForm({ kind, item })} refresh={refresh} />}
        {page === 'dues' && <Obligations data={data} refresh={refresh} showChecks={() => setPage('checks')} />}
        {page === 'checks' && <><button className="back-link" onClick={() => setPage('dues')}>بازگشت به سررسیدها</button><Checks data={data} refresh={refresh}/></>}
        {page === 'insights' && <Insights back={() => setPage('more')} />}
        {page === 'alerts' && <Alerts back={() => { refresh(); setPage('more') }} onChanged={refresh} />}
        {page === 'assets' && <Assets data={data} open={(kind, item, holding) => setForm({ kind, item, holding })} refresh={refresh} />}
        {page === 'more' && <More data={data} open={(kind, item) => setForm({ kind, item })} refresh={refresh} profile={() => setPage('profile')} insights={() => setPage('insights')} alerts={() => setPage('alerts')} checks={() => setPage('checks')} logout={async () => { await write('auth/logout/', {}); setUser(null); setData(null) }} />}
        {page === 'profile' && <Profile user={user} theme={theme} setTheme={setTheme} back={() => setPage('more')} />}
      </>}
    </main><nav className="bottom-nav" aria-label="ناوبری اصلی">{nav.map(item => <button key={item.id} aria-current={page === item.id ? 'page' : undefined} className={page === item.id || (item.id === 'more' && ['profile','insights','alerts'].includes(page)) || (item.id === 'dues' && page === 'checks') ? 'selected' : ''} onClick={() => { setForm(null); setPage(item.id); window.scrollTo(0, 0) }}><item.icon size={21}/><span>{item.label}</span></button>)}</nav>
    {form && <Form kind={form.kind} item={form.item} holding={form.holding} data={data} error={error} close={() => { setForm(null); setError('') }} submit={submit} />}
  </div>
}

function Login({ onSuccess }) {
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [error, setError] = useState(''), [showPassword, setShowPassword] = useState(false)
  async function submit(e) { e.preventDefault(); try { setError(''); await onSuccess(await write('auth/login/', { username, password })) } catch (ex) { setError(ex.message) } }
  return <div className="login"><div className="login-card"><div className="brand-mark">P</div><div className="eyebrow">Phinance</div><h1>مدیریت آسان پول</h1><p>دخل‌وخرج، دارایی‌ها و سررسیدهای خانه در یک جا.</p><form onSubmit={submit}><label>نام کاربری<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required/></label><label>رمز عبور<div className="password-field"><input type={showPassword ? 'text' : 'password'} autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/><button type="button" aria-label={showPassword ? 'پنهان کردن رمز عبور' : 'نمایش رمز عبور'} aria-pressed={showPassword} onClick={() => setShowPassword(value => !value)}>{showPassword ? <EyeOff size={20}/> : <Eye size={20}/>}</button></div></label>{error && <div className="error">{error}</div>}<button className="primary">ورود</button></form></div></div>
}

function HomePage({ data, navigate, open }) {
  const d = data.dashboard
  const upcoming = data.obligations.filter(item => item.status !== 'settled').sort((a, b) => a.due_date.localeCompare(b.due_date))
  return <><section className="hero"><div className="hero-top"><span>خالص دارایی</span><button onClick={() => navigate('insights')} aria-label="دیدن گزارش‌ها"><TrendingUp size={19}/></button></div><div className="hero-number">{money(d.net_worth)}</div><div className="hero-stats"><div><span>موجودی حساب‌ها</span><strong>{money(d.account_total)}</strong></div><div><span>جریان پول این ماه</span><strong>{money(d.monthly_net)}</strong></div></div></section>
    {!data.accounts.length && <div className="start-card"><strong>اولین حساب را بسازید</strong><span>تا بتوانید درآمد و هزینه ثبت کنید.</span><button onClick={() => open('account')}>افزودن حساب</button></div>}
    <div className="quick"><button className="quick-expense" onClick={() => open('expense')}><ArrowUpLeft size={21}/> ثبت هزینه</button><button className="quick-income" onClick={() => open('income')}><ArrowDownRight size={21}/> ثبت درآمد</button></div>
    <div className="section-title"><h2>این ماه</h2><button onClick={() => navigate('insights')}>گزارش‌ها <ChevronLeft size={16}/></button></div>
    <div className="monthly"><div><span>درآمد</span><strong className="positive">{money(d.monthly_income)}</strong></div><div><span>هزینه</span><strong className="negative">{money(d.monthly_expense)}</strong></div></div>
    <div className="section-title"><h2>سررسیدهای نزدیک</h2><button onClick={() => navigate('dues')}>همه <ChevronLeft size={16}/></button></div>
    {upcoming.length ? <div className="card-list">{upcoming.slice(0, 2).map(item => <div className="summary-row" key={item.id}><div className="iconbox"><CalendarDays size={19}/></div><div><strong>{item.counterparty}</strong><small>{item.is_overdue ? 'سررسید گذشته' : new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium' }).format(new Date(item.due_date + 'T12:00:00'))}</small></div><b>{money(item.remaining_amount)}</b></div>)}</div> : <div className="empty compact-empty">سررسید بازی ندارید.</div>}
    <div className="section-title"><h2>آخرین تراکنش‌ها</h2><button onClick={() => navigate('transactions')}>همه <ChevronLeft size={16}/></button></div>
    {data.transactions.length ? <div className="card-list">{data.transactions.slice(0, 3).map(t => <div className="transaction-row" key={t.id}><div className={'tx-icon ' + t.type}>{t.type === 'income' ? <ArrowDownRight size={18}/> : <ArrowUpLeft size={18}/>}</div><div><strong>{t.description || t.category_name || 'انتقال پول'}</strong><small>{new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium' }).format(new Date(t.date + 'T12:00:00'))}</small></div><b className={t.type === 'income' ? 'positive' : t.type === 'expense' ? 'negative' : ''}>{money(t.amount)}</b></div>)}</div> : <div className="empty compact-empty">هنوز تراکنشی ثبت نشده است.</div>}
  </>
}

function Transactions({ data, open, refresh }) {
  const [filter, setFilter] = useState('all')
  const items = data.transactions.filter(t => filter === 'all' || (filter === 'debt' ? t.type.startsWith('debt_') || t.type.startsWith('loan_') : t.type === filter))
  const groups = items.reduce((result, item) => { (result[item.date] ||= []).push(item); return result }, {})
  return <><div className="page-actions"><button className="solid-action" onClick={() => open('expense')}><ArrowUpLeft size={19}/> هزینه</button><button onClick={() => open('income')}><ArrowDownRight size={19}/> درآمد</button><button onClick={() => open('transfer')}><ArrowLeftRight size={19}/> انتقال</button></div><div className="tabs">{[['all','همه'],['expense','هزینه‌ها'],['income','درآمدها'],['transfer','انتقال‌ها'],['debt','وام و بدهی']].map(([id,label]) => <button key={id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div>
    {Object.entries(groups).length ? Object.entries(groups).map(([date, txs]) => <section key={date}><div className="date-heading">{new Intl.DateTimeFormat('fa-IR', { dateStyle: 'long' }).format(new Date(date + 'T12:00:00'))}</div><div className="card-list">{txs.map(t => {
      const incoming = ['income','debt_receipt','loan_borrowed'].includes(t.type)
      const outgoing = ['expense','debt_payment','loan_lent'].includes(t.type)
      return <div className="transaction-row" key={t.id}><div className={'tx-icon ' + t.type}>{incoming ? <ArrowDownRight/> : outgoing ? <ArrowUpLeft/> : <ArrowLeftRight/>}</div><div><strong>{t.description || t.category_name || 'انتقال پول'}</strong><small>{t.type === 'transfer' ? `${t.source_name} ← ${t.destination_name}` : outgoing ? t.source_name : t.destination_name}</small>{!t.is_linked && ['income','expense','transfer'].includes(t.type) && <RecordActions label={t.description || t.category_name || 'تراکنش'} path={`transactions/${t.id}/`} onEdit={() => open(t.type, t)} refresh={refresh} warning="این تراکنش از موجودی و گزارش‌ها حذف می‌شود."/>}</div><b className={incoming ? 'positive' : outgoing ? 'negative' : ''}>{incoming ? '+' : outgoing ? '−' : ''}{money(t.amount)}</b></div>
    })}</div></section>) : <Empty text="هنوز تراکنشی ثبت نشده است."/>}
    </>
}

function Assets({ data, open, refresh }) { return <><div className="asset-feature"><div><span>ارزش فعلی طلا</span><strong>{money(data.gold.current_value)}</strong><small>{number(data.gold.weight_grams)} گرم · سرمایه باقی‌مانده {money(data.gold.amount_invested)}</small><details className="asset-price-details"><summary>قیمت روز و به‌روزرسانی</summary><small>هر گرم طلای ۱۸ عیار: {money(data.gold.price_per_gram)}</small><small>{data.gold.price_updated_at ? `آخرین به‌روزرسانی: ${new Intl.DateTimeFormat('fa-IR', { dateStyle:'medium', timeStyle:'short' }).format(new Date(data.gold.price_updated_at))}` : 'قیمت خودکار هنوز دریافت نشده است.'}</small></details></div><div className="asset-actions"><button onClick={() => open('gold')}>افزودن طلا</button></div></div>
    <div className="section-title"><h2>طلاهای من</h2></div><div className="gold-list">{data.purchases.length ? data.purchases.map(g => <article className="gold-card" key={g.id}><div className="gold-card-head"><div><span className="gold-mark">◇</span><div><h3>{g.name}</h3><small>خرید {new Intl.DateTimeFormat('fa-IR', { dateStyle:'medium' }).format(new Date(g.purchase_date + 'T12:00:00'))} · وزن اولیه {number(g.weight_grams)} گرم</small></div></div><strong>{number(g.remaining_weight_grams)} گرم باقی‌مانده</strong></div><div className="gold-values"><div><small>پرداخت اولیه</small><b>{money(g.amount_paid)}</b></div><div><small>ارزش فعلی</small><b>{money(g.current_value)}</b></div><div><small>سود / زیان</small><b className={g.profit_loss >= 0 ? 'positive' : 'negative'}>{money(g.profit_loss)}</b></div></div>{Number(g.remaining_weight_grams) > 0 && <button className="sell-gold" onClick={() => open('gold-sale', null, g)}>ثبت فروش</button>}<RecordActions label={g.name} path={`gold-purchases/${g.id}/`} onEdit={() => open('gold', g)} refresh={refresh}/></article>) : <Empty text="هنوز طلایی ثبت نشده است."/>}</div>
    {data.sales.length > 0 && <><div className="section-title"><h2>فروش‌های طلا</h2></div><div className="card-list">{data.sales.map(sale => <div className="summary-row" key={sale.id}><div className="iconbox gold">◇</div><div><strong>{sale.holding_name}</strong><small>{new Intl.DateTimeFormat('fa-IR', { dateStyle:'medium' }).format(new Date(sale.sale_date + 'T12:00:00'))} · {number(sale.weight_grams)} گرم</small><RecordActions label={`فروش ${sale.holding_name}`} path={`gold-sales/${sale.id}/`} onEdit={() => open('gold-sale', sale, data.purchases.find(g => g.id === sale.purchase))} refresh={refresh} warning="مبلغ فروش از حساب کم و وزن طلا بازگردانده می‌شود."/></div><b>{money(sale.amount_received)}</b></div>)}</div></>}
    <div className="section-title"><h2>دارایی‌های دیگر</h2><button onClick={() => open('asset')}><Plus size={17}/> افزودن</button></div><div className="card-list">{data.assets.filter(a => a.active).length ? data.assets.filter(a => a.active).map(a => <div className="summary-row" key={a.id}><div className="iconbox">⌂</div><div><strong>{a.name}</strong><small>{({property:'ملک',vehicle:'خودرو',investment:'سرمایه‌گذاری',other:'سایر'})[a.asset_type]}</small><RecordActions label={a.name} path={`assets/${a.id}/`} onEdit={() => open('asset', a)} refresh={refresh} warning="این دارایی از برآورد خالص دارایی حذف می‌شود."/></div><b>{money(a.current_value)}</b></div>) : <Empty text="دارایی دیگری ثبت نشده است."/>}</div></> }

function More({ data, open, refresh, profile, insights, alerts, checks, logout }) { return <>
  <div className="more-links">
    <button className="profile-link" onClick={insights}><div className="iconbox"><TrendingUp size={20}/></div><div><strong>گزارش‌ها</strong><small>روند درآمد و هزینه</small></div><ChevronLeft size={18}/></button>
    <button className="profile-link" onClick={checks}><div className="iconbox"><CalendarDays size={20}/></div><div><strong>چک‌ها</strong><small>دریافتی و پرداختی</small></div><ChevronLeft size={18}/></button>
    <button className="profile-link" onClick={alerts}><div className="iconbox"><Bell size={20}/></div><div><strong>اعلان‌ها</strong><small>یادآوری‌ها و تنظیمات</small></div><ChevronLeft size={18}/></button>
    <button className="profile-link" onClick={profile}><div className="iconbox"><UserRound size={20}/></div><div><strong>پروفایل</strong><small>ظاهر برنامه</small></div><ChevronLeft size={18}/></button>
  </div>
  <div className="section-title"><h2>حساب‌ها</h2><button onClick={() => open('account')}><Plus size={17}/> افزودن</button></div>
  <div className="card-list">{data.accounts.length ? data.accounts.map(a => <div className="summary-row" key={a.id}><div className="iconbox"><Wallet size={20}/></div><div><strong>{a.name}</strong><small>{({cash:'نقد',bank:'بانک',wallet:'کیف پول'})[a.account_type]}{!a.active && ' · غیرفعال'}</small>{a.active ? <RecordActions label={a.name} path={`accounts/${a.id}/`} onEdit={() => open('account', a)} refresh={refresh} deleteLabel="غیرفعال کردن" warning="حساب برای حفظ تاریخچه مالی غیرفعال می‌شود. می‌توانید آن را بعداً از ویرایش دوباره فعال کنید."/> : <button className="category-add" onClick={() => open('account', a)}>ویرایش یا فعال‌سازی</button>}</div><b>{money(a.balance)}</b></div>) : <Empty text="برای شروع یک حساب بسازید."/>}</div>
  <details className="manage-categories"><summary>مدیریت دسته‌ها</summary><button className="category-add" onClick={() => open('category')}>افزودن دسته</button>{data.categories.map(category => <div className="category-row" key={category.id}><div><strong>{category.name}</strong><small>{category.type === 'income' ? 'درآمد' : 'هزینه'}</small></div><RecordActions label={category.name} path={`categories/${category.id}/`} onEdit={() => open('category', category)} refresh={refresh} warning="این دسته حذف می‌شود. دسته‌های استفاده‌شده در سوابق مالی قابل حذف نیستند."/></div>)}</details>
  <button className="logout" onClick={logout}><LogOut size={18}/> خروج از حساب</button></> }
function Profile({ user, theme, setTheme, back }) { return <><button className="back-link" onClick={back}><ChevronLeft size={18}/> بازگشت به بیشتر</button><section className="profile-card"><div className="profile-avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><div className="eyebrow">حساب کاربری</div><h2>{user.username}</h2></div></section><section className="preference-card"><div className="setting-heading"><div className="iconbox"><Settings size={21}/></div><div><h2>ظاهر برنامه</h2><p>حالت دلخواه خود را انتخاب کنید.</p></div></div><div className="theme-options"><button className={theme === 'light' ? 'chosen' : ''} onClick={() => setTheme('light')}><Sun size={22}/><span>روشن</span><small>زمینه روشن و آرام</small></button><button className={theme === 'dark' ? 'chosen' : ''} onClick={() => setTheme('dark')}><Moon size={22}/><span>تیره</span><small>برای محیط‌های کم‌نور</small></button></div></section></> }
function Empty({ text }) { return <div className="empty">{text}</div> }

function Form({ kind, item, holding, data, error, close, submit }) {
  const [v, setV] = useState(() => ({ date: today(), purchase_date: today(), sale_date: today(), price_per_gram: item?.amount_received && item?.weight_grams ? Math.round(item.amount_received / Number(item.weight_grams)) : data.gold.price_per_gram || '', type: kind, account_type: 'bank', asset_type: 'property', category_type: 'expense',
    ...(item && (['income','expense','transfer'].includes(kind) ? { amount: String(item.amount), date: item.date, source_account: item.source_account || '', destination_account: item.destination_account || '', category: item.category || '', description: item.description || '' }
      : kind === 'account' ? { name: item.name, account_type: item.account_type, opening_balance: String(item.opening_balance), active: item.active }
      : kind === 'category' ? { name: item.name, category_type: item.type }
      : kind === 'asset' ? { name: item.name, asset_type: item.asset_type, acquisition_cost: String(item.acquisition_cost), current_value: String(item.current_value) }
      : kind === 'gold' ? { name: item.name, purchase_date: item.purchase_date, weight_grams: item.weight_grams, amount_paid: String(item.amount_paid), description: item.description || '' }
      : kind === 'gold-sale' ? { sale_date: item.sale_date, weight_grams: item.weight_grams, account: item.account } : {})) }))
  const set = (key, value) => setV(old => ({ ...old, [key]: value }))
  const title = (item ? 'ویرایش ' : '') + ({ expense:'هزینه', income:'درآمد', transfer:'انتقال پول', account:'حساب', category:'دسته', asset:'دارایی', gold:'طلا', 'gold-sale':'فروش طلا' })[kind]
  const accounts = data.accounts.filter(a => a.active)
  function save(e) {
    e.preventDefault()
    const amount = key => Number(String(v[key] || '').replace(/[٬,\s]/g, ''))
    const path = base => item ? `${base}${item.id}/` : base
    const method = item ? 'PATCH' : 'POST'
    if (['expense','income','transfer'].includes(kind)) submit(path('transactions/'), { type: kind, amount: amount('amount'), date: v.date, source_account: kind === 'income' ? null : Number(v.source_account), destination_account: kind === 'expense' ? null : Number(v.destination_account), category: kind === 'transfer' ? null : Number(v.category), description: v.description || '' }, method)
    if (kind === 'account') submit(path('accounts/'), { name: v.name, account_type: v.account_type, opening_balance: amount('opening_balance'), active: v.active ?? true }, method)
    if (kind === 'category') submit(path('categories/'), { name: v.name, type: v.category_type }, method)
    if (kind === 'asset') submit(path('assets/'), { name: v.name, asset_type: v.asset_type, acquisition_cost: amount('acquisition_cost'), current_value: amount('current_value') }, method)
    if (kind === 'gold') submit(path('gold-purchases/'), { name: v.name, purchase_date: v.purchase_date, weight_grams: v.weight_grams, amount_paid: amount('amount_paid'), description: v.description || '' }, method)
    if (kind === 'gold-sale') submit(path('gold-sales/'), { purchase: holding.id, account: Number(v.account), sale_date: v.sale_date, weight_grams: v.weight_grams, price_per_gram: amount('price_per_gram') }, method)
  }
  const input = (label, key, props = {}) => {
    const { money: isMoney, type, ...inputProps } = props
    if (type === 'date') return <JalaliField key={key} label={label} value={v[key]} onChange={value => set(key, value)}/>
    if (isMoney) return <label key={key} className="money-input-field">{label}<input value={formatAmountInput(v[key])} onChange={e => set(key, normalizeDigits(e.target.value).replace(/[^0-9]/g, ''))} required {...inputProps}/><small className="amount-in-words" aria-live="polite">{amountInPersianWords(v[key]) || 'مبلغ به حروف'}</small></label>
    return <label key={key}>{label}<input value={v[key] || ''} onChange={e => set(key, e.target.value)} required {...(type ? { type } : {})} {...inputProps}/></label>
  }
  const select = (label, key, choices) => <label>{label}<select value={v[key] || ''} onChange={e => set(key, e.target.value)} required><option value="">انتخاب کنید</option>{choices.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
  return <div className="overlay" onClick={close}><div className="sheet" onClick={e => e.stopPropagation()}><div className="sheet-head"><h2>{title}</h2><button onClick={close} aria-label="بستن">×</button></div><form onSubmit={save}>
    {['expense','income','transfer'].includes(kind) && <>{input('مبلغ (تومان)', 'amount', { money:true, inputMode:'numeric' })}{kind !== 'transfer' && select('دسته', 'category', data.categories.filter(c => c.type === kind).map(c => [c.id,c.name]))}{kind !== 'income' && select(kind === 'transfer' ? 'از حساب' : 'حساب', 'source_account', accounts.map(a => [a.id,a.name]))}{kind !== 'expense' && select(kind === 'transfer' ? 'به حساب' : 'حساب', 'destination_account', accounts.map(a => [a.id,a.name]))}<details className="form-extra"><summary>تاریخ و توضیح</summary>{input('تاریخ', 'date', { type:'date' })}{kind !== 'transfer' && input('توضیح (اختیاری)', 'description', { required:false, placeholder:'مثلاً خرید از سوپرمارکت' })}</details></>}
    {kind === 'account' && <>{input('نام حساب', 'name', { placeholder:'مثلاً بانک ملی' })}{select('نوع حساب', 'account_type', [['bank','بانک'],['cash','نقد'],['wallet','کیف پول']])}{input(item ? 'موجودی اولیه (تومان)' : 'موجودی فعلی (تومان)', 'opening_balance', { money:true, inputMode:'numeric' })}{item && <label>وضعیت حساب<select value={v.active ? 'active' : 'inactive'} onChange={e => set('active', e.target.value === 'active')}><option value="active">فعال</option><option value="inactive">غیرفعال</option></select></label>}</>}
    {kind === 'category' && <>{input('نام دسته', 'name')}{select('نوع دسته', 'category_type', [['expense','هزینه'],['income','درآمد']])}</>}
    {kind === 'asset' && <>{input('نام دارایی', 'name', { placeholder:'مثلاً خانه' })}{select('نوع دارایی', 'asset_type', [['property','ملک'],['vehicle','خودرو'],['investment','سرمایه‌گذاری'],['other','سایر']])}{input('ارزش فعلی (تومان)', 'current_value', { money:true, inputMode:'numeric' })}{input('هزینه خرید (تومان)', 'acquisition_cost', { money:true, inputMode:'numeric' })}</>}
    {kind === 'gold' && <>{input('نام طلا', 'name', { placeholder:'مثلاً دستبند یا سکه' })}{input('وزن (گرم)', 'weight_grams', { type:'number', min:0.001, step:0.001, inputMode:'decimal' })}{input('مبلغ پرداختی (تومان)', 'amount_paid', { money:true, inputMode:'numeric' })}{input('تاریخ خرید', 'purchase_date', { type:'date' })}{input('توضیح (اختیاری)', 'description', { required:false })}</>}
    {kind === 'gold-sale' && <><div className="sale-holding">{holding.name} · باقی‌مانده {number(holding.remaining_weight_grams)} گرم</div>{input('وزن فروش (گرم)', 'weight_grams', { type:'number', min:0.001, max:Number(holding.remaining_weight_grams) + Number(item?.weight_grams || 0), step:0.001, inputMode:'decimal' })}{input('قیمت فروش هر گرم (تومان)', 'price_per_gram', { money:true, inputMode:'numeric' })}{select('واریز وجه به حساب', 'account', accounts.map(a => [a.id, `${a.name} · ${money(a.balance)}`]))}{input('تاریخ فروش', 'sale_date', { type:'date' })}<p className="hint">فروش طلا درآمد محسوب نمی‌شود و مبلغ آن به موجودی حساب انتخاب‌شده اضافه خواهد شد.</p></>}
    {error && <div className="error" role="alert">{error}</div>}<button className="primary">{item ? 'ذخیره تغییرات' : 'ثبت و ذخیره'}</button></form></div></div>
}
export default App
