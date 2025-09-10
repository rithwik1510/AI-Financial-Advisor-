import axios from 'axios'

// Configure axios base URL from build-time env (Vite)
const API_BASE = (import.meta as any)?.env?.VITE_API_BASE_URL || ''
if (API_BASE) {
  axios.defaults.baseURL = API_BASE
}

export interface Transaction {
  date?: string | null
  description?: string | null
  amount: number
  currency?: string | null
  category?: string | null
  account?: string | null
  source?: string | null
}

export interface AnalyzeResult {
  summary: { transactions: number; total_inflow: number; total_outflow: number; net: number }
  monthly: { month: string; income: number; expenses: number; net: number; tx_count: number }[]
  by_category: { category: string; amount: number }[]
  by_merchant: { description: string | null; total_spend: number; total_inflow: number; tx_count: number }[]
  savings_rate: number
  dti?: number | null
  emergency_fund_months?: number | null
  discretionary_share?: number | null
  health_score?: number | null
  insights: string[]
  anomalies: any[]
  recurring: any[]
  budget_variance?: { category: string; actual: number; target: number; variance: number }[]
}

// ----- Tools API -----
export interface MortgagePaymentInput {
  principal?: number
  house_price?: number
  down_payment?: number
  down_payment_percent?: number
  annual_rate: number
  term_years?: number
  monthly_taxes?: number
  property_tax_rate_annual?: number
  monthly_insurance?: number
  insurance_rate_annual?: number
  monthly_hoa?: number
  monthly_pmi?: number
  pmi_rate_annual?: number
  ltv_pmi_threshold?: number
}

export interface MortgagePaymentResult {
  house_price?: number
  down_payment?: number
  principal: number
  annual_rate: number
  term_months: number
  monthly_pi: number
  monthly_taxes: number
  monthly_insurance: number
  monthly_hoa: number
  monthly_pmi: number
  monthly_piti: number
}

export interface AffordabilityInput {
  monthly_income: number
  monthly_debt_payments: number
  annual_rate: number
  term_years?: number
  down_payment?: number
  down_payment_percent?: number
  property_tax_rate_annual?: number
  insurance_rate_annual?: number
  monthly_hoa?: number
  pmi_rate_annual?: number
  ltv_pmi_threshold?: number
  dti_front?: number
  dti_back?: number
}

export interface AffordabilityResult {
  max_price: number
  binding_constraint: string
  piti_at_max: number
  breakdown: { pi: number; taxes: number; insurance: number; hoa: number; pmi: number }
  assumptions: Record<string, any>
}

export async function apiToolMortgagePayment(input: MortgagePaymentInput): Promise<MortgagePaymentResult> {
  const { data } = await axios.post('/api/tools/mortgage_payment', input)
  return data
}

export async function apiToolAffordability(input: AffordabilityInput): Promise<AffordabilityResult> {
  const { data } = await axios.post('/api/tools/affordability', input)
  return data
}

export interface ParseResponse {
  transactions: Transaction[]
  files: string[]
  notes?: string
  dq_score?: number
  dq?: any
  warnings?: string[]
}

export async function apiParse(files: File[]): Promise<ParseResponse> {
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  // Do NOT set Content-Type manually; let browser set proper boundary
  const { data } = await axios.post('/api/parse', form)
  return data
}

export async function apiAnalyze(
  transactions: Transaction[],
  extra?: {
    liquid_savings?: number
    monthly_debt_payments?: number
    budgets?: Record<string, number>
    category_rules?: { match_type?: 'contains' | 'regex'; pattern: string; category: string }[]
  }
): Promise<AnalyzeResult> {
  const payload = { transactions, ...(extra || {}) }
  const { data } = await axios.post('/api/analyze', payload)
  return data
}

export async function apiAsk(analytics: AnalyzeResult | null, question: string, model?: string): Promise<{ answer: string; model: string }> {
  const payload = { analytics, question, model }
  const { data } = await axios.post('/api/ask', payload)
  return data
}

export async function apiSaveTemplate(tpl: {
  name: string
  anchors: string[]
  columns: { date: [number, number]; description: [number, number]; amount: [number, number] }
  date_format?: string
}): Promise<{ status: string; path: string }> {
  const { data } = await axios.post('/api/templates', tpl)
  return data
}

export async function apiLlmStatus(): Promise<{ ok: boolean; provider: string; model: string; error?: string | null }> {
  const { data } = await axios.get('/api/llm/status')
  return data
}

// Document Q&A not supported with OpenAI-only build
