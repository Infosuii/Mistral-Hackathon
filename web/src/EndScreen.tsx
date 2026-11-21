import { ElectionFinale } from './Election'
import type { GameState } from './state'

const scoreLabels = {
  months_in_power: 'Months in power',
  peace_months: 'Months at peace',
  gdp_change: 'Economy change',
  stability_change: 'Stability change',
  promises_kept: 'Promises kept',
  promises_broken: 'Promises broken',
}
const endReasons: Record<string, string> = {
  ended: 'You ended the session.',
  voted_out: 'Your leader was voted out.',
  coup: 'A coup removed your leader from office.',
  time: 'Your three-year term is over.',
}

const signed = new Intl.NumberFormat('en', { signDisplay: 'exceptZero', maximumFractionDigits: 1 })
const percent = new Intl.NumberFormat('en', { style: 'percent' })
const scoreKeys = Object.keys(scoreLabels) as (keyof typeof scoreLabels)[]

export function EndScreen({ state, online }: { state: GameState; online: boolean }) {
  const ending = state.ending
  const dispatches = state.news.slice(-3).reverse()
  const seat = state.seat.nation ? state.nations[state.seat.nation]?.name : 'Independent mediator'
  const score = ending?.score
  const metrics: [string, string | number][] = []
  if (score && state.seat.role === 'mediator') {
    if (score.peaceful_crises != null) metrics.push(['Peaceful crises', score.peaceful_crises])
    if (score.average_trust != null) metrics.push(['Average trust', percent.format(score.average_trust)])
  } else if (score) {
    for (const key of scoreKeys) {
      const value = key === 'gdp_change' || key === 'stability_change' ? signed.format(score[key]) : score[key]
      metrics.push([scoreLabels[key], value])
    }
  }
  return (
    <main className="ending-screen">
      <article className="ending-sheet" aria-labelledby="ending-heading">
        <header>
          {seat && <p className="subtle">{seat}</p>}
          <h2 id="ending-heading">Session complete</h2>
          {ending?.reason && <p className="ending-reason">{endReasons[ending.reason] ?? ending.reason.replaceAll('_', ' ')}</p>}
        </header>
        <ElectionFinale state={state} />
        {metrics.length > 0 && (
          <dl className="ending-score" data-mediator={state.seat.role === 'mediator'}>
            {metrics.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        )}
        <section className="historian-verdict" aria-labelledby="historian-heading">
          <h3 id="historian-heading">The historian’s verdict</h3>
          {ending?.verdict ? (
            <blockquote>{ending.verdict}</blockquote>
          ) : <p role="status">{ending && online ? 'Waiting for the historian’s verdict.' : 'No verdict has arrived.'}</p>}
        </section>
        {dispatches.length > 0 && (
          <section className="ending-dispatches" aria-labelledby="ending-dispatches-heading">
            <h3 id="ending-dispatches-heading">Final dispatches</h3>
            <ol>
              {dispatches.map(({ turn, text }, index) => (
                <li key={`${turn}-${index}`}><span>Month {turn}</span><p>{text}</p></li>
              ))}
            </ol>
          </section>
        )}
      </article>
    </main>
  )
}
