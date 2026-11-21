import type { GameState, SessionScore } from './state'

const scoreLabels: Record<keyof SessionScore, string> = {
  months_in_power: 'Months in power',
  peace_months: 'Months at peace',
  gdp_change: 'Economy change',
  stability_change: 'Stability change',
  promises_kept: 'Promises kept',
  promises_broken: 'Promises broken',
}
const signed = new Intl.NumberFormat('en', { signDisplay: 'exceptZero', maximumFractionDigits: 1 })
const scoreKeys = Object.keys(scoreLabels) as (keyof SessionScore)[]

export function EndScreen({ state, online }: { state: GameState; online: boolean }) {
  const ending = state.ending
  const dispatches = state.news.slice(-3).reverse()
  const seat = state.seat.nation ? state.nations[state.seat.nation]?.name : undefined
  return (
    <main className="ending-screen">
      <article className="ending-sheet" aria-labelledby="ending-heading">
        <header>
          {seat && <p className="subtle">{seat}</p>}
          <h2 id="ending-heading">Session complete</h2>
          {ending?.reason && <p className="ending-reason">{ending.reason.replaceAll('_', ' ')}</p>}
        </header>
        {ending && (
          <dl className="ending-score">
            {scoreKeys.map((key) => (
              <div key={key}>
                <dt>{scoreLabels[key]}</dt>
                <dd>{key === 'gdp_change' || key === 'stability_change' ? signed.format(ending.score[key]) : ending.score[key]}</dd>
              </div>
            ))}
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
