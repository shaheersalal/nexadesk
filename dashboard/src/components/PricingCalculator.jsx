import { useState } from 'react'
import { Sparkles } from 'lucide-react'

import { API_BASE as API } from '../lib/apiBase'

// Local mirror of the backend formula (app/pricing/router.py) — used only for
// instant slider/card feedback. The real price for any "Offer" action always
// comes from POST /pricing/calculate, since a browser-JS price is devtools-editable.
const BASE_FEE = 99
const INCLUDED_MINUTES = 200
const PER_MINUTE_OVERAGE = 0.18
const PER_EXTRA_SEAT = 35

function estimatePrice(minutes, seats) {
  const overage = Math.max(0, minutes - INCLUDED_MINUTES) * PER_MINUTE_OVERAGE
  const extraSeats = Math.max(0, seats - 1) * PER_EXTRA_SEAT
  return Math.round((BASE_FEE + overage + extraSeats) * 100) / 100
}

const TIERS = [
  { name: 'Starter', minutes: 200, seats: 1, blurb: 'Solo agents getting started' },
  { name: 'Growth', minutes: 600, seats: 3, blurb: 'Small teams scaling outreach', highlight: true },
  { name: 'Scale', minutes: 1500, seats: 6, blurb: 'Full agencies, high call volume' },
]

export default function PricingCalculator({ onOffer }) {
  const [minutes, setMinutes] = useState(400)
  const [seats, setSeats] = useState(2)
  const [offering, setOffering] = useState(null)

  async function handleOffer(m, s) {
    const key = `${m}-${s}`
    setOffering(key)
    try {
      const res = await fetch(`${API}/pricing/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ minutes: m, seats: s }),
      })
      const data = await res.json()
      onOffer({ minutes: m, seats: s, price: data.price })
    } catch {
      onOffer({ minutes: m, seats: s, price: estimatePrice(m, s) })
    } finally {
      setOffering(null)
    }
  }

  return (
    <div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
        {TIERS.map(t => {
          const price = estimatePrice(t.minutes, t.seats)
          const key = `${t.minutes}-${t.seats}`
          return (
            <div
              key={t.name}
              className={`rounded-2xl border p-6 flex flex-col bg-white ${
                t.highlight ? 'border-accent shadow-lg shadow-accent/10 relative' : 'border-gray-200'
              }`}
            >
              {t.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 bg-accent text-white text-[10px] font-semibold px-3 py-1 rounded-full">
                  MOST POPULAR
                </span>
              )}
              <h3 className="font-semibold text-gray-900 mb-1">{t.name}</h3>
              <p className="text-xs text-gray-400 mb-4">{t.blurb}</p>
              <p className="text-3xl font-black text-gray-900 mb-1">
                ${price}<span className="text-sm font-normal text-gray-400">/mo</span>
              </p>
              <p className="text-xs text-gray-400 mb-6">{t.minutes} min · {t.seats} seat{t.seats > 1 ? 's' : ''}</p>
              <button
                onClick={() => handleOffer(t.minutes, t.seats)}
                disabled={offering === key}
                className={`mt-auto w-full py-2.5 rounded-xl font-semibold text-sm transition-colors disabled:opacity-60 ${
                  t.highlight ? 'bg-accent text-white hover:bg-accent-dark' : 'bg-navy-600 text-white hover:bg-navy-700'
                }`}
              >
                {offering === key ? 'Loading…' : 'Offer'}
              </button>
            </div>
          )
        })}
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-6 md:p-8">
        <div className="flex items-center gap-2 mb-6">
          <Sparkles className="w-4 h-4 text-accent" />
          <h3 className="font-semibold text-gray-900">Build your own plan</h3>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-gray-600">Monthly minutes</label>
              <span className="text-sm font-semibold text-gray-900">{minutes}</span>
            </div>
            <input
              type="range" min={100} max={3000} step={50} value={minutes}
              onChange={e => setMinutes(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm text-gray-600">Seats</label>
              <span className="text-sm font-semibold text-gray-900">{seats}</span>
            </div>
            <input
              type="range" min={1} max={15} step={1} value={seats}
              onChange={e => setSeats(Number(e.target.value))}
              className="w-full accent-accent"
            />
          </div>
        </div>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <p className="text-2xl font-black text-gray-900">
            ${estimatePrice(minutes, seats)}<span className="text-sm font-normal text-gray-400">/mo</span>
          </p>
          <button
            onClick={() => handleOffer(minutes, seats)}
            disabled={offering === `${minutes}-${seats}`}
            className="bg-navy-600 text-white font-semibold px-6 py-2.5 rounded-xl hover:bg-navy-700 transition-colors disabled:opacity-60"
          >
            {offering === `${minutes}-${seats}` ? 'Loading…' : 'Offer'}
          </button>
        </div>
      </div>
    </div>
  )
}
