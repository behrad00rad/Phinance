import React, { useEffect, useState } from 'react'
import { Home, ArrowLeftRight, Wallet, Shapes, MoreHorizontal, Plus, ArrowUpLeft, ArrowDownRight, ChevronLeft, LogOut, UserRound, Sun, Moon, Settings } from 'lucide-react'
import { api, write } from './api'

const money = value => new Intl.NumberFormat('fa-IR').format(Number(value || 0)) + ' تومان'
const number = value => new Intl.NumberFormat('fa-IR').format(Number(value || 0))
const today = () => new Date().toLocaleDateString('en-CA')
const nav = [{ id: 'home', label: 'خانه', icon: Home }, { id: 'transactions', label: 'تراکنش‌ها', icon: ArrowLeftRight }, { id: 'assets', label: 'دارایی‌ها', icon: Shapes }, { id: 'more', label: 'بیشتر', icon: MoreHorizontal }]

function App() {
  const [user, setUser] = useState(null), [page, setPage] = useState('home'), [data, setData] = useState(null)
  const [error, setError] = useState(''), [loading, setLoading] = useState(true), [form, setForm] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('phinance-theme') || 'light')
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('phinance-theme', theme) }, [theme])
  async function refresh() {
    try {
      const [dashboard, accounts, categories, transactions, assets, gold, purchases] = await Promise.all([
        api('dashboard/'), api('accounts/'), api('categories/'), api('transactions/'), api('assets/'), api('gold/summary/'), api('gold-purchases/')])
      setData({ dashboard, accounts, categories, transactions, assets, gold, purchases })
    } catch (e) { setError(e.message) }
  }
  useEffect(() => { (async () => { try { await api('auth/csrf/'); setUser(await api('auth/me/')); await refresh() } catch {} finally { setLoading(false) } })() }, [])
  async function submit(path, payload, method = 'POST') { try { setError(''); await write(path, payload, method); setForm(null); await refresh() } catch (e) { setError(e.message) } }
  if (loading) return <div className="center">در حال بارگذاری…</div>
  if (!user) return <Login onSuccess={async u => { setUser(u); await refresh() }} />
  return <div className="app"><header className="top"><div><div className="eyebrow">خانه‌حساب</div><h1>{page === 'home' ? 'سلام، خوش آمدید' : page === 'profile' ? 'پروفایل و تنظیمات' : nav.find(x => x.id === page)?.label}</h1></div><div className="avatar">خ</div></header>
    <main>
      {error && <div className="error" role="alert">{error}<button onClick={() => setError('')}>×</button></div>}
      {!data ? <p>در حال بارگذاری…</p> : <>
        {page === 'home' && <HomePage data={data} navigate={setPage} open={setForm} />}
        {page === 'transactions' && <Transactions data={data} open={setForm} />}
        {page === 'assets' && <Assets data={data} open={setForm} />}
        {page === 'more' && <More data={data} open={setForm} profile={() => setPage('profile')} logout={async () => { await write('auth/logout/', {}); setUser(null); setData(null) }} />}
        {page === 'profile' && <Profile user={user} theme={theme} setTheme={setTheme} back={() => setPage('more')} />}
      </>}
    </main><nav className="bottom-nav">{nav.map(item => <button key={item.id} className={page === item.id ? 'selected' : ''} onClick={() => setPage(item.id)}><item.icon size={23}/><span>{item.label}</span></button>)}</nav>
    {form && <Form kind={form} data={data} error={error} close={() => { setForm(null); setError('') }} submit={submit} />}
  </div>
}

function Login({ onSuccess }) {
  const [username, setUsername] = useState(''), [password, setPassword] = useState(''), [error, setError] = useState('')
  async function submit(e) { e.preventDefault(); try { setError(''); await onSuccess(await write('auth/login/', { username, password })) } catch (ex) { setError(ex.message) } }
  return <div className="login"><div className="login-card"><div className="brand-mark">خ</div><div className="eyebrow">خانه‌حساب</div><h1>حساب خانواده، ساده و روشن</h1><p>برای دیدن دارایی‌ها و ثبت دخل‌وخرج وارد شوید.</p><form onSubmit={submit}><label>نام کاربری<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required/></label><label>رمز عبور<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required/></label>{error && <div className="error">{error}</div>}<button className="primary">ورود به خانه‌حساب</button></form></div></div>
}

function HomePage({ data, navigate, open }) {
  const d = data.dashboard
  return <><section className="hero"><div className="eyebrow light">نمای کلی خانواده</div><div className="hero-label">دارایی کل</div><div className="hero-number">{money(d.net_worth)}</div><div className="hero-foot">مجموع پول و دارایی‌های ثبت‌شده</div></section>
    {!data.accounts.length && <div className="start-card"><strong>از اولین حساب شروع کنید</strong><span>برای ثبت درآمد و هزینه، یک حساب بانکی یا پول نقد بسازید.</span><button onClick={() => open('account')}>افزودن حساب</button></div>}
    <div className="section-title"><h2>این ماه</h2><span>{new Intl.DateTimeFormat('fa-IR', { month: 'long', year: 'numeric' }).format(new Date())}</span></div>
    <div className="monthly"><div><span>درآمد</span><strong className="positive">{money(d.monthly_income)}</strong></div><div><span>هزینه</span><strong className="negative">{money(d.monthly_expense)}</strong></div><div><span>خالص جریان پول</span><strong>{money(d.monthly_net)}</strong></div></div>
    <div className="quick"><button className="quick-expense" onClick={() => open('expense')}><ArrowUpLeft size={25}/> ثبت هزینه</button><button className="quick-income" onClick={() => open('income')}><ArrowDownRight size={25}/> ثبت درآمد</button></div>
    <button className="text-action" onClick={() => open('transfer')}><ArrowLeftRight size={19}/> انتقال پول بین حساب‌ها <ChevronLeft size={17}/></button>
    <div className="section-title"><h2>پول و دارایی‌ها</h2><button onClick={() => navigate('assets')}>دیدن همه <ChevronLeft size={16}/></button></div>
    <div className="card-list"><div className="summary-row"><div className="iconbox">☰</div><div><strong>حساب‌ها و پول نقد</strong><small>{data.accounts.length} حساب</small></div><b>{money(d.account_total)}</b></div><div className="summary-row"><div className="iconbox gold">◈</div><div><strong>طلا</strong><small>{number(d.gold.weight_grams)} گرم</small></div><b>{money(d.gold.current_value)}</b></div><div className="summary-row"><div className="iconbox">⌂</div><div><strong>سایر دارایی‌ها</strong><small>{data.assets.length} مورد</small></div><b>{money(d.asset_total)}</b></div></div>
  </>
}

function Transactions({ data, open }) {
  const [filter, setFilter] = useState('all')
  const items = data.transactions.filter(t => filter === 'all' || t.type === filter)
  const groups = items.reduce((result, item) => { (result[item.date] ||= []).push(item); return result }, {})
  return <><div className="page-intro">دخل‌وخرج خانواده در یک نگاه</div><div className="tabs">{[['all','همه'],['expense','هزینه‌ها'],['income','درآمدها'],['transfer','انتقال‌ها']].map(([id,label]) => <button key={id} className={filter === id ? 'active' : ''} onClick={() => setFilter(id)}>{label}</button>)}</div>
    {Object.entries(groups).length ? Object.entries(groups).map(([date, txs]) => <section key={date}><div className="date-heading">{new Intl.DateTimeFormat('fa-IR', { dateStyle: 'long' }).format(new Date(date + 'T12:00:00'))}</div><div className="card-list">{txs.map(t => <div className="transaction-row" key={t.id}><div className={'tx-icon ' + t.type}>{t.type === 'expense' ? <ArrowUpLeft/> : t.type === 'income' ? <ArrowDownRight/> : <ArrowLeftRight/>}</div><div><strong>{t.description || t.category_name || 'انتقال پول'}</strong><small>{t.type === 'transfer' ? `${t.source_name} ← ${t.destination_name}` : t.type === 'expense' ? t.source_name : t.destination_name}</small></div><b className={t.type === 'income' ? 'positive' : t.type === 'expense' ? 'negative' : ''}>{t.type === 'income' ? '+' : t.type === 'expense' ? '−' : ''}{money(t.amount)}</b></div>)}</div></section>) : <Empty text="هنوز تراکنشی ثبت نشده است."/>}
    <button className="floating" onClick={() => open('expense')}><Plus/> ثبت هزینه</button></>
}

function Assets({ data, open }) { return <><div className="page-intro">همه آنچه خانواده دارد</div><div className="asset-feature"><div><span>ارزش طلای شما</span><strong>{money(data.gold.current_value)}</strong><small>{number(data.gold.weight_grams)} گرم طلا · سرمایه‌گذاری {money(data.gold.amount_invested)}</small></div><div className="asset-actions"><button onClick={() => open('gold')}>ثبت خرید طلا</button><button onClick={() => open('price')}>قیمت هر گرم: {money(data.gold.price_per_gram)}</button></div></div>
    <div className="section-title"><h2>دارایی‌های دیگر</h2><button onClick={() => open('asset')}><Plus size={17}/> افزودن</button></div><div className="card-list">{data.assets.length ? data.assets.filter(a => a.active).map(a => <div className="summary-row" key={a.id}><div className="iconbox">⌂</div><div><strong>{a.name}</strong><small>{({property:'ملک',vehicle:'خودرو',investment:'سرمایه‌گذاری',other:'سایر'})[a.asset_type]}</small></div><b>{money(a.current_value)}</b></div>) : <Empty text="دارایی دیگری ثبت نشده است."/>}</div></> }

function More({ data, open, profile, logout }) { return <><div className="page-intro">مدیریت ساده حساب‌های خانواده</div><button className="profile-link" onClick={profile}><div className="iconbox"><UserRound size={21}/></div><div><strong>پروفایل و تنظیمات</strong><small>نمایش و انتخاب حالت صفحه</small></div><ChevronLeft size={19}/></button><div className="section-title"><h2>حساب‌ها</h2><button onClick={() => open('account')}><Plus size={17}/> افزودن حساب</button></div><div className="card-list">{data.accounts.length ? data.accounts.map(a => <div className="summary-row" key={a.id}><div className="iconbox"><Wallet size={21}/></div><div><strong>{a.name}</strong><small>{({cash:'نقد',bank:'بانک',wallet:'کیف پول'})[a.account_type]}{!a.active && ' · غیرفعال'}</small></div><b>{money(a.balance)}</b></div>) : <Empty text="برای شروع یک حساب بسازید."/>}</div><button className="logout" onClick={logout}><LogOut size={18}/> خروج از حساب</button></> }
function Profile({ user, theme, setTheme, back }) { return <><button className="back-link" onClick={back}><ChevronLeft size={18}/> بازگشت به بیشتر</button><section className="profile-card"><div className="profile-avatar">{user.username.slice(0, 1).toUpperCase()}</div><div><div className="eyebrow">حساب کاربری</div><h2>{user.username}</h2></div></section><section className="preference-card"><div className="setting-heading"><div className="iconbox"><Settings size={21}/></div><div><h2>ظاهر برنامه</h2><p>حالت دلخواه خود را انتخاب کنید.</p></div></div><div className="theme-options"><button className={theme === 'light' ? 'chosen' : ''} onClick={() => setTheme('light')}><Sun size={22}/><span>روشن</span><small>زمینه روشن و آرام</small></button><button className={theme === 'dark' ? 'chosen' : ''} onClick={() => setTheme('dark')}><Moon size={22}/><span>تیره</span><small>برای محیط‌های کم‌نور</small></button></div></section></> }
function Empty({ text }) { return <div className="empty">{text}</div> }

function Form({ kind, data, error, close, submit }) {
  const [v, setV] = useState({ date: today(), purchase_date: today(), type: kind, account_type: 'bank', asset_type: 'property' })
  const set = (key, value) => setV(old => ({ ...old, [key]: value }))
  const title = ({ expense:'ثبت هزینه', income:'ثبت درآمد', transfer:'انتقال پول', account:'حساب جدید', asset:'دارایی جدید', gold:'ثبت خرید طلا', price:'قیمت روز طلا' })[kind]
  const accounts = data.accounts.filter(a => a.active)
  function save(e) {
    e.preventDefault()
    const amount = key => Number(String(v[key] || '').replace(/[٬,\s]/g, ''))
    if (['expense','income','transfer'].includes(kind)) submit('transactions/', { type: kind, amount: amount('amount'), date: v.date, source_account: kind === 'income' ? null : Number(v.source_account), destination_account: kind === 'expense' ? null : Number(v.destination_account), category: kind === 'transfer' ? null : Number(v.category), description: v.description || '' })
    if (kind === 'account') submit('accounts/', { name: v.name, account_type: v.account_type, opening_balance: amount('opening_balance'), description: '' })
    if (kind === 'asset') submit('assets/', { name: v.name, asset_type: v.asset_type, acquisition_cost: amount('acquisition_cost'), current_value: amount('current_value'), notes: '' })
    if (kind === 'gold') submit('gold-purchases/', { purchase_date: v.purchase_date, weight_grams: v.weight_grams, amount_paid: amount('amount_paid'), description: v.description || '' })
    if (kind === 'price') submit('gold/price/', { price_per_gram: amount('price_per_gram') }, 'PUT')
  }
  const input = (label, key, props = {}) => <label>{label}<input value={v[key] || ''} onChange={e => set(key, e.target.value)} required {...props}/></label>
  const select = (label, key, choices) => <label>{label}<select value={v[key] || ''} onChange={e => set(key, e.target.value)} required><option value="">انتخاب کنید</option>{choices.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
  return <div className="overlay" onClick={close}><div className="sheet" onClick={e => e.stopPropagation()}><div className="sheet-head"><h2>{title}</h2><button onClick={close} aria-label="بستن">×</button></div><form onSubmit={save}>
    {['expense','income','transfer'].includes(kind) && <>{input('مبلغ (تومان)', 'amount', { inputMode:'numeric', type:'number', min:1 })}{kind !== 'transfer' && select('دسته', 'category', data.categories.filter(c => c.type === kind).map(c => [c.id,c.name]))}{kind !== 'income' && select(kind === 'transfer' ? 'از حساب' : 'حساب', 'source_account', accounts.map(a => [a.id,a.name]))}{kind !== 'expense' && select(kind === 'transfer' ? 'به حساب' : 'حساب', 'destination_account', accounts.map(a => [a.id,a.name]))}{kind === 'transfer' && input('تاریخ', 'date', { type:'date' })}{kind !== 'transfer' && input('توضیح (اختیاری)', 'description', { required:false, placeholder:'مثلاً خرید از سوپرمارکت' })}</>}
    {kind === 'account' && <>{input('نام حساب', 'name', { placeholder:'مثلاً بانک ملی' })}{select('نوع حساب', 'account_type', [['bank','بانک'],['cash','نقد'],['wallet','کیف پول']])}{input('موجودی فعلی (تومان)', 'opening_balance', { type:'number', min:0, inputMode:'numeric' })}</>}
    {kind === 'asset' && <>{input('نام دارایی', 'name', { placeholder:'مثلاً خانه' })}{select('نوع دارایی', 'asset_type', [['property','ملک'],['vehicle','خودرو'],['investment','سرمایه‌گذاری'],['other','سایر']])}{input('ارزش فعلی (تومان)', 'current_value', { type:'number', min:0, inputMode:'numeric' })}{input('هزینه خرید (تومان)', 'acquisition_cost', { type:'number', min:0, inputMode:'numeric' })}</>}
    {kind === 'gold' && <>{input('وزن (گرم)', 'weight_grams', { type:'number', min:0.001, step:0.001, inputMode:'decimal' })}{input('مبلغ پرداختی (تومان)', 'amount_paid', { type:'number', min:1, inputMode:'numeric' })}{input('تاریخ خرید', 'purchase_date', { type:'date' })}{input('توضیح (اختیاری)', 'description', { required:false })}</>}
    {kind === 'price' && <>{input('قیمت فعلی هر گرم (تومان)', 'price_per_gram', { type:'number', min:0, inputMode:'numeric' })}<p className="hint">این قیمت فقط برای برآورد ارزش طلای شما استفاده می‌شود.</p></>}
    {error && <div className="error" role="alert">{error}</div>}<button className="primary">ثبت و ذخیره</button></form></div></div>
}
export default App
