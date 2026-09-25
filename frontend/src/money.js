const persianDigits = '۰۱۲۳۴۵۶۷۸۹'
const arabicDigits = '٠١٢٣٤٥٦٧٨٩'

export function normalizeDigits(value) {
  return String(value ?? '').replace(/[۰-۹٠-٩]/g, digit => {
    const persianIndex = persianDigits.indexOf(digit)
    return String(persianIndex === -1 ? arabicDigits.indexOf(digit) : persianIndex)
  })
}

export function formatAmountInput(value) {
  const digits = normalizeDigits(value).replace(/[^0-9]/g, '')
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
}

const ones = ['صفر', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
const teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
const tens = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
const hundreds = ['', 'صد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد']
const scales = ['', 'هزار', 'میلیون', 'میلیارد', 'تریلیون', 'کوادریلیون']

function threeDigitsToWords(number) {
  const parts = []
  const hundred = Math.floor(number / 100)
  const rest = number % 100
  if (hundred) parts.push(hundreds[hundred])
  if (rest >= 10 && rest < 20) parts.push(teens[rest - 10])
  else {
    if (rest >= 20) parts.push(tens[Math.floor(rest / 10)])
    if (rest % 10) parts.push(ones[rest % 10])
  }
  return parts.join(' و ')
}

export function amountInPersianWords(value) {
  const digits = normalizeDigits(value).replace(/[^0-9]/g, '').replace(/^0+/, '')
  if (!digits) return value ? 'صفر تومان' : ''
  const groups = []
  for (let end = digits.length; end > 0; end -= 3) groups.unshift(digits.slice(Math.max(0, end - 3), end))
  const words = groups.map((group, index) => {
    const n = Number(group)
    const scale = groups.length - index - 1
    if (!n) return ''
    return [threeDigitsToWords(n), scales[scale] || ''].filter(Boolean).join(' ')
  }).filter(Boolean)
  return `${words.join(' و ')} تومان`
}
