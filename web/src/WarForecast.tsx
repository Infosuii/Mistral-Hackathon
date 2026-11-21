import type { CSSProperties } from 'react'
import type { Futures } from './state'

const toAngle = (probability: number) => 180 * probability - 90
const percent = new Intl.NumberFormat('en', { style: 'percent' })

export function WarForecast({ forecast }: { forecast: Futures | null }) {
  const before = forecast?.before.war_p ?? 0
  const after = forecast?.after.war_p ?? 0

  return (
    <section className="panel forecast" aria-labelledby="forecast-heading">
      <h2 id="forecast-heading">War odds in six months</h2>
      {forecast ? (
        <>
          <div className="forecast-body">
            <svg viewBox="0 0 160 80" className="forecast-dial" aria-hidden="true">
              <defs>
                <linearGradient id="forecast-colours">
                  <stop offset="0%" stopColor="var(--trade)" />
                  <stop offset="55%" stopColor="var(--accent)" />
                  <stop offset="100%" stopColor="var(--war)" />
                </linearGradient>
              </defs>
              <path className="forecast-arc" d="M20 75 A60 60 0 0 1 140 75" />
              <line className="forecast-marker" x1="80" y1="19" x2="80" y2="28"
                transform={`rotate(${toAngle(before)} 80 75)`} />
              <line key={`${before}|${after}`} className="forecast-needle" x1="80" y1="75" x2="80" y2="24"
                style={{ '--needle-before': `${toAngle(before)}deg`, '--needle-after': `${toAngle(after)}deg` } as CSSProperties} />
              <circle cx="80" cy="75" r="4" />
            </svg>
            <dl>
              <div><dt>Before</dt><dd>{percent.format(before)}</dd></div>
              <div><dt>After</dt><dd>{percent.format(after)}</dd></div>
            </dl>
          </div>
          <p className="forecast-caption">{forecast.caption}</p>
        </>
      ) : <p className="forecast-caption">Awaiting a call that changes the outlook.</p>}
    </section>
  )
}
