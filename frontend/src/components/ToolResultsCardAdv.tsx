import { useState } from 'react'
import { AnalyzeResult, apiToolAffordability, apiToolMortgagePayment } from '../api'

export default function ToolResultsCardAdv({
  index,
  results,
  missing,
  analytics,
  onUpdate,
}: {
  index: number
  results: any
  missing: string[]
  analytics: AnalyzeResult | null
  onUpdate: (idx: number, newResults: any) => void
}) {
  const mp = results?.mortgage_payment
  const af = results?.affordability
  const hasAny = !!mp || !!af || (missing && missing.length > 0)
  if (!hasAny) return null

  const [openMp, setOpenMp] = useState(true)
  const [openAf, setOpenAf] = useState(true)
  const [editing, setEditing] = useState<'mp'|'af'|null>(null)
  const [mpForm, setMpForm] = useState<any>({
    annual_rate: mp?.annual_rate ?? 0.065,
    term_years: mp?.term_months ? Math.round(mp.term_months/12) : 30,
    house_price: mp?.house_price ?? undefined,
    principal: mp?.principal ?? undefined,
    down_payment: mp?.down_payment ?? undefined,
    down_payment_percent: undefined as number|undefined,
    property_tax_rate_annual: 0.0125,
    insurance_rate_annual: 0.003,
    monthly_hoa: mp?.monthly_oa ?? mp?.monthly_hoa ?? 0,
    pmi_rate_annual: 0.006,
    ltv_pmi_threshold: 0.80,
  })
  const avgMonthlyIncome = analytics?.monthly && analytics.monthly.length ? Math.max(0, analytics.monthly.map(m=>m.income).reduce((a,b)=>a+b,0)/analytics.monthly.length) : 0
  const [afForm, setAfForm] = useState<any>({
    monthly_income: Math.round(avgMonthlyIncome),
    monthly_debt_payments:  analytics?.dti && avgMonthlyIncome ? Math.round((analytics.dti||0)*avgMonthlyIncome) : 0,
    annual_rate: 0.065,
    term_years: 30,
    down_payment_percent: 0.20,
    property_tax_rate_annual: 0.0125,
    insurance_rate_annual: 0.003,
    monthly_hoa: 0,
    pmi_rate_annual: 0.006,
    ltv_pmi_threshold: 0.80,
    dti_front: 0.28,
    dti_back: 0.36,
  })

  const runMp = async () => {
    const out = await apiToolMortgagePayment({ ...mpForm })
    onUpdate(index, { mortgage_payment: out })
    setEditing(null)
  }
  const runAf = async () => {
    const out = await apiToolAffordability({ ...afForm })
    onUpdate(index, { affordability: out })
    setEditing(null)
  }
  const copySummary = async () => {
    const parts: string[] = []
    if (mp) parts.push(`Mortgage Payment — PITI $${mp.monthly_piti} (PI $${mp.monthly_pi}, Taxes $${mp.monthly_taxes}, Ins $${mp.monthly_insurance}${mp.monthly_hoa?`, HOA $${mp.monthly_hoa}`:''}${mp.monthly_pmi?`, PMI $${mp.monthly_pmi}`:''}) at ${(mp.annual_rate*100).toFixed(2)}% for ${mp.term_months} mo`)
    if (af) parts.push(`Affordability — Max Price $${af.max_price} (PITI $${af.piti_at_max}) • Binding: ${af.binding_constraint}`)
    try { await navigator.clipboard.writeText(parts.join('\n')) } catch {}
  }

  return (
    <div className="border border-zinc-800/70 rounded-xl bg-zinc-900/40">
      <div className="p-3 border-b border-zinc-800/60 text-zinc-300 text-sm flex items-center justify-between">
        <span>Tool Results</span>
        <div className="flex items-center gap-2">
          <button onClick={copySummary} className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200">Copy</button>
        </div>
      </div>
      <div className="p-3 grid gap-3 md:grid-cols-2">
        {mp && (
          <div className="rounded-lg bg-zinc-900/50 border border-zinc-800/60 p-3">
            <div className="font-medium text-zinc-100 flex items-center justify-between">
              <span>Mortgage Payment</span>
              <div className="flex items-center gap-2">
                <button className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setEditing(editing==='mp'?null:'mp')}>{editing==='mp'?'Close':'Edit assumptions'}</button>
                <button className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setOpenMp(!openMp)}>{openMp?'Hide':'Show'}</button>
              </div>
            </div>
            {openMp && (
              <>
                <div className="mt-1 text-sm text-zinc-300">Rate: {(mp.annual_rate*100).toFixed(2)}% • Term: {mp.term_months} mo</div>
                <div className="mt-2 text-sm text-zinc-200">
                  <div>PI: ${mp.monthly_pi.toFixed ? mp.monthly_pi.toFixed(2) : mp.monthly_pi}</div>
                  <div>Taxes: ${mp.monthly_taxes.toFixed ? mp.monthly_taxes.toFixed(2) : mp.monthly_taxes}</div>
                  <div>Insurance: ${mp.monthly_insurance.toFixed ? mp.monthly_insurance.toFixed(2) : mp.monthly_insurance}</div>
                  {mp.monthly_hoa ? <div>HOA: ${mp.monthly_hoa.toFixed ? mp.monthly_hoa.toFixed(2) : mp.monthly_hoa}</div> : null}
                  {mp.monthly_pmi ? <div>PMI: ${mp.monthly_pmi.toFixed ? mp.monthly_pmi.toFixed(2) : mp.monthly_pmi}</div> : null}
                  <div className="mt-1 font-semibold">PITI: ${mp.monthly_piti.toFixed ? mp.monthly_piti.toFixed(2) : mp.monthly_piti}</div>
                </div>
              </>
            )}
            {editing==='mp' && (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-200">
                <label>Rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(mpForm.annual_rate*100).toString()} onChange={e=>setMpForm({...mpForm, annual_rate: Number(e.target.value)/100})} /></label>
                <label>Term (yrs)<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={mpForm.term_years} onChange={e=>setMpForm({...mpForm, term_years: Number(e.target.value)})} /></label>
                <label>House Price<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={mpForm.house_price||''} onChange={e=>setMpForm({...mpForm, house_price: e.target.value===''?undefined:Number(e.target.value)})} /></label>
                <label>Down Payment<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={mpForm.down_payment||''} onChange={e=>setMpForm({...mpForm, down_payment: e.target.value===''?undefined:Number(e.target.value)})} /></label>
                <label>DP %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={mpForm.down_payment_percent??''} onChange={e=>setMpForm({...mpForm, down_payment_percent: e.target.value===''?undefined:Number(e.target.value)})} /></label>
                <label>Tax rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(mpForm.property_tax_rate_annual*100).toString()} onChange={e=>setMpForm({...mpForm, property_tax_rate_annual: Number(e.target.value)/100})} /></label>
                <label>Ins rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(mpForm.insurance_rate_annual*100).toString()} onChange={e=>setMpForm({...mpForm, insurance_rate_annual: Number(e.target.value)/100})} /></label>
                <label>HOA $/mo<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={mpForm.monthly_hoa} onChange={e=>setMpForm({...mpForm, monthly_hoa: Number(e.target.value)})} /></label>
                <div className="col-span-2 flex justify-end gap-2 mt-1">
                  <button className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setEditing(null)}>Cancel</button>
                  <button className="px-3 py-1 rounded bg-gradient-to-br from-purple-600 to-fuchsia-600 text-white hover:from-purple-500 hover:to-fuchsia-500" onClick={runMp}>Update</button>
                </div>
              </div>
            )}
          </div>
        )}

        {af && (
          <div className="rounded-lg bg-zinc-900/50 border border-zinc-800/60 p-3">
            <div className="font-medium text-zinc-100 flex items-center justify-between">
              <span>Affordability</span>
              <div className="flex items-center gap-2">
                <button className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setEditing(editing==='af'?null:'af')}>{editing==='af'?'Close':'Edit assumptions'}</button>
                <button className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setOpenAf(!openAf)}>{openAf?'Hide':'Show'}</button>
              </div>
            </div>
            {openAf && (
              <>
                <div className="mt-1 text-sm text-zinc-300">Binding: {af.binding_constraint} • PITI at max: ${af.piti_at_max.toFixed ? af.piti_at_max.toFixed(2) : af.piti_at_max}</div>
                <div className="mt-2 text-sm text-zinc-200">
                  <div>Max Price: ${af.max_price.toLocaleString?.() || af.max_price}</div>
                  {af.breakdown && (
                    <div className="mt-1 text-zinc-300">
                      <div>PI: ${af.breakdown.pi.toFixed ? af.breakdown.pi.toFixed(2) : af.breakdown.pi}</div>
                      <div>Taxes: ${af.breakdown.taxes.toFixed ? af.breakdown.taxes.toFixed(2) : af.breakdown.taxes}</div>
                      <div>Ins: ${af.breakdown.insurance.toFixed ? af.breakdown.insurance.toFixed(2) : af.breakdown.insurance}</div>
                      {af.breakdown.hoa ? <div>HOA: ${af.breakdown.hoa.toFixed ? af.breakdown.hoa.toFixed(2) : af.breakdown.hoa}</div> : null}
                      {af.breakdown.pmi ? <div>PMI: ${af.breakdown.pmi.toFixed ? af.breakdown.pmi.toFixed(2) : af.breakdown.pmi}</div> : null}
                    </div>
                  )}
                </div>
              </>
            )}
            {editing==='af' && (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-zinc-200">
                <label>Monthly income<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={afForm.monthly_income} onChange={e=>setAfForm({...afForm, monthly_income: Number(e.target.value)})} /></label>
                <label>Monthly debts<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={afForm.monthly_debt_payments} onChange={e=>setAfForm({...afForm, monthly_debt_payments: Number(e.target.value)})} /></label>
                <label>Rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(afForm.annual_rate*100).toString()} onChange={e=>setAfForm({...afForm, annual_rate: Number(e.target.value)/100})} /></label>
                <label>Term (yrs)<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={afForm.term_years} onChange={e=>setAfForm({...afForm, term_years: Number(e.target.value)})} /></label>
                <label>Down %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={afForm.down_payment_percent} onChange={e=>setAfForm({...afForm, down_payment_percent: Number(e.target.value)})} /></label>
                <label>Tax rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(afForm.property_tax_rate_annual*100).toString()} onChange={e=>setAfForm({...afForm, property_tax_rate_annual: Number(e.target.value)/100})} /></label>
                <label>Ins rate %<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" step="0.01" value={(afForm.insurance_rate_annual*100).toString()} onChange={e=>setAfForm({...afForm, insurance_rate_annual: Number(e.target.value)/100})} /></label>
                <label>HOA $/mo<input className="w-full mt-1 bg-zinc-950 border border-zinc-800 rounded p-1" type="number" value={afForm.monthly_hoa} onChange={e=>setAfForm({...afForm, monthly_hoa: Number(e.target.value)})} /></label>
                <div className="col-span-2 flex justify-end gap-2 mt-1">
                  <button className="px-3 py-1 rounded bg-zinc-800 hover:bg-zinc-700" onClick={()=>setEditing(null)}>Cancel</button>
                  <button className="px-3 py-1 rounded bg-gradient-to-br from-purple-600 to-fuchsia-600 text-white hover:from-purple-500 hover:to-fuchsia-500" onClick={runAf}>Update</button>
                </div>
              </div>
            )}
          </div>
        )}

        {missing && missing.length > 0 && (
          <div className="rounded-lg bg-amber-950/30 border border-amber-800/60 p-3 text-amber-200">
            <div className="font-medium">Missing Inputs</div>
            <div className="text-sm mt-1">Please provide: {missing.join(', ')}</div>
          </div>
        )}
      </div>
    </div>
  )
}

