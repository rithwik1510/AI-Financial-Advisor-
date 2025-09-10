import { useEffect, useMemo, useState } from 'react'
import { AnalyzeResult, apiAnalyze, Transaction } from '../api'
import { Pie, Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement
} from 'chart.js'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, PointElement, LineElement)

interface Props {
  transactions: Transaction[]
  analytics: AnalyzeResult | null
  setAnalytics: (a: AnalyzeResult) => void
}

export default function Dashboard({ transactions, analytics, setAnalytics }: Props) {
  const [liquidSavings, setLiquidSavings] = useState<string>(() => {
    try { return localStorage.getItem('liquid_savings') || '' } catch { return '' }
  })
  const [monthlyDebt, setMonthlyDebt] = useState<string>(() => {
    try { return localStorage.getItem('monthly_debt_payments') || '' } catch { return '' }
  })
  const [budgets, setBudgets] = useState<Record<string, number>>(() => {
    try { return JSON.parse(localStorage.getItem('budgets') || '{}') } catch { return {} }
  })
  const [newBudgetCat, setNewBudgetCat] = useState('')
  const [newBudgetAmt, setNewBudgetAmt] = useState('')

  useEffect(() => {
    try {
      localStorage.setItem('liquid_savings', liquidSavings)
      localStorage.setItem('monthly_debt_payments', monthlyDebt)
    } catch {}
  }, [liquidSavings, monthlyDebt])

  useEffect(() => {
    try { localStorage.setItem('budgets', JSON.stringify(budgets)) } catch {}
  }, [budgets])

  useEffect(() => {
    const run = async () => {
      if (transactions.length === 0) return
      const extra: any = {}
      const ls = Number(liquidSavings)
      const md = Number(monthlyDebt)
      if (!Number.isNaN(ls) && liquidSavings !== '') extra.liquid_savings = ls
      if (!Number.isNaN(md) && monthlyDebt !== '') extra.monthly_debt_payments = md
      if (budgets && Object.keys(budgets).length > 0) extra.budgets = budgets
      const res = await apiAnalyze(transactions, extra)
      setAnalytics(res)
    }
    run()
  }, [transactions, liquidSavings, monthlyDebt, budgets])

  const pieData = useMemo(() => {
    if (!analytics) return null
    const labels = analytics.by_category.map(c => c.category)
    const data = analytics.by_category.map(c => Math.abs(c.amount))
    return {
      labels,
      datasets: [{ label: 'Spending by Category', data, backgroundColor: labels.map((_, i) => `hsl(${(i*47)%360} 70% 60%)`) }]
    }
  }, [analytics])

  const lineData = useMemo(() => {
    if (!analytics) return null
    const labels = analytics.monthly.map(m => m.month)
    return {
      labels,
      datasets: [
        { label: 'Income', data: analytics.monthly.map(m => m.income), borderColor: '#10b981' },
        { label: 'Expenses', data: analytics.monthly.map(m => Math.abs(m.expenses)), borderColor: '#ef4444' },
        { label: 'Net', data: analytics.monthly.map(m => m.net), borderColor: '#3b82f6' },
      ]
    }
  }, [analytics])

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
        <h3 className="font-semibold mb-2">Assumptions</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <label className="text-sm">
            <span className="block text-gray-700 mb-1">Liquid savings (USD)</span>
            <input
              className="w-full border rounded px-3 py-2"
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 5000"
              value={liquidSavings}
              onChange={(e) => setLiquidSavings(e.target.value)}
            />
          </label>
          <label className="text-sm">
            <span className="block text-gray-700 mb-1">Monthly debt payments (USD)</span>
            <input
              className="w-full border rounded px-3 py-2"
              type="number"
              min="0"
              step="0.01"
              placeholder="e.g. 300"
              value={monthlyDebt}
              onChange={(e) => setMonthlyDebt(e.target.value)}
            />
          </label>
        </div>
        <p className="text-xs text-gray-500 mt-2">Used to compute DTI and emergency fund months. Leave blank if unknown.</p>
      </div>
      <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
        <h3 className="font-semibold mb-2">Budgets (Monthly Targets)</h3>
        <div className="flex flex-wrap items-end gap-2 text-sm">
          <label className="text-sm">
            <span className="block text-gray-700 mb-1">Category</span>
            <input className="w-48 border rounded px-3 py-2" value={newBudgetCat} onChange={e=>setNewBudgetCat(e.target.value)} placeholder="e.g. Dining" />
          </label>
          <label className="text-sm">
            <span className="block text-gray-700 mb-1">Target (USD/mo)</span>
            <input className="w-40 border rounded px-3 py-2" type="number" min="0" step="1" value={newBudgetAmt} onChange={e=>setNewBudgetAmt(e.target.value)} placeholder="200" />
          </label>
          <button
            className="px-3 py-2 rounded bg-indigo-600 hover:bg-indigo-700 text-white"
            onClick={() => {
              const cat = newBudgetCat.trim(); const amt = Number(newBudgetAmt)
              if (!cat || Number.isNaN(amt)) return
              setBudgets(prev => ({ ...prev, [cat]: amt }))
              setNewBudgetCat(''); setNewBudgetAmt('')
            }}
          >Add</button>
        </div>
        {Object.keys(budgets).length > 0 ? (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Target</th>
                  <th className="py-2 pr-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(budgets).map(([cat, amt]) => (
                  <tr key={cat} className="border-t">
                    <td className="py-2 pr-4">{cat}</td>
                    <td className="py-2 pr-4">
                      <input className="w-28 border rounded px-2 py-1" type="number" value={amt} onChange={e => {
                        const v = Number(e.target.value)
                        setBudgets(prev => ({ ...prev, [cat]: Number.isNaN(v) ? amt : v }))
                      }} />
                    </td>
                    <td className="py-2 pr-4">
                      <button className="text-red-600 hover:underline" onClick={() => {
                        setBudgets(prev => { const cp={...prev} as any; delete cp[cat]; return cp })
                      }}>Remove</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm mt-2">No budgets set. Add targets to track against your spending.</p>
        )}
      </div>
      <div className="bg-white p-4 rounded shadow-sm">
        <h3 className="font-semibold mb-2">Summary</h3>
        {analytics ? (
          <ul className="text-sm space-y-1">
            <li>Transactions: {analytics.summary.transactions}</li>
            <li>Total Income: ${analytics.summary.total_inflow.toFixed(2)}</li>
            <li>Total Expenses: ${Math.abs(analytics.summary.total_outflow).toFixed(2)}</li>
            <li>Net: ${analytics.summary.net.toFixed(2)}</li>
            <li>Savings Rate: {(analytics.savings_rate * 100).toFixed(1)}%</li>
            {analytics.dti != null && <li>DTI: {(analytics.dti * 100).toFixed(1)}%</li>}
            {analytics.emergency_fund_months != null && <li>Emergency Fund: {analytics.emergency_fund_months.toFixed(1)} months</li>}
            {analytics.discretionary_share != null && <li>Discretionary Share: {(analytics.discretionary_share * 100).toFixed(0)}%</li>}
            {analytics.health_score != null && <li>Health Score: {analytics.health_score.toFixed(0)}/100</li>}
          </ul>
        ) : (
          <p className="text-gray-600 text-sm">Upload statements to see your dashboard.</p>
        )}
      </div>

      <div className="bg-white p-4 rounded shadow-sm">
        <h3 className="font-semibold mb-2">Spending by Category</h3>
        {pieData ? <Pie data={pieData} /> : <p className="text-gray-600 text-sm">No data</p>}
      </div>

      <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
        <h3 className="font-semibold mb-2">Monthly Trends</h3>
        {lineData ? <Line data={lineData} /> : <p className="text-gray-600 text-sm">No data</p>}
      </div>

      {analytics && analytics.budget_variance && (
        <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
          <h3 className="font-semibold mb-2">Budgets vs Actual (Avg Monthly)</h3>
          {analytics.budget_variance.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-600">
                    <th className="py-2 pr-4">Category</th>
                    <th className="py-2 pr-4">Actual</th>
                    <th className="py-2 pr-4">Target</th>
                    <th className="py-2 pr-4">Variance</th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.budget_variance.map((r, idx) => (
                    <tr key={idx} className="border-t">
                      <td className="py-2 pr-4">{r.category}</td>
                      <td className="py-2 pr-4">${r.actual.toFixed(2)}</td>
                      <td className="py-2 pr-4">${r.target.toFixed(2)}</td>
                      <td className={`py-2 pr-4 ${r.variance > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{r.variance > 0 ? '+' : ''}${r.variance.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-gray-600 text-sm">No matching budget categories yet.</p>
          )}
        </div>
      )}

      <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
        <h3 className="font-semibold mb-2">Recurring</h3>
        {analytics && analytics.recurring && analytics.recurring.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead>
                <tr className="text-left text-gray-600">
                  <th className="py-2 pr-4">Description</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Typical</th>
                  <th className="py-2 pr-4">Frequency</th>
                  <th className="py-2 pr-4">Occurrences</th>
                  <th className="py-2 pr-4">Next</th>
                </tr>
              </thead>
              <tbody>
                {analytics.recurring.map((r: any, idx: number) => (
                  <tr key={idx} className="border-t">
                    <td className="py-2 pr-4">{r.description}</td>
                    <td className="py-2 pr-4 capitalize">{r.type}</td>
                    <td className="py-2 pr-4">${Math.abs(r.typical_amount).toFixed(2)}</td>
                    <td className="py-2 pr-4">{r.frequency}{r.confidence ? ` (${r.confidence})` : ''}</td>
                    <td className="py-2 pr-4">{r.occurrences}</td>
                    <td className="py-2 pr-4">{r.next_estimated_date ? String(r.next_estimated_date).slice(0, 10) : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm">No recurring items detected.</p>
        )}
      </div>

      <div className="bg-white p-4 rounded shadow-sm md:col-span-2">
        <h3 className="font-semibold mb-2">Insights</h3>
        {analytics && analytics.insights.length > 0 ? (
          <ul className="list-disc ml-6 text-sm">
            {analytics.insights.map((i, idx) => <li key={idx}>{i}</li>)}
          </ul>
        ) : (
          <p className="text-gray-600 text-sm">No insights yet.</p>
        )}
      </div>
    </div>
  )
}
