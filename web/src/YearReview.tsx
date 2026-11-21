import { useEffect, type CSSProperties } from 'react'
import type { GameState } from './state'
import { theme } from './theme'
import './election.css'

// The engine logs a "year_review" event at the end of each year of the three-year term but the
// last (the end screen holds the final election). Extra fields come from engine/core.py.
export interface ReviewEvent {
  turn: number
  type: string
  nation?: string | null
  year?: number
  years?: number
  approval?: number
  approval_start?: number
  stability?: number
  stability_start?: number
  gdp?: number
  gdp_start?: number
  election_held?: boolean
  wars?: number
}

const SHOW_MS = 7_000
const THRESHOLD = 45  // data/weights.json politics.election_min_approval
const signed = new Intl.NumberFormat('en', { signDisplay: 'exceptZero', maximumFractionDigits: 0 })

export function latestReview(state: GameState): ReviewEvent | null {
  const review = [...state.events].reverse().find((event) => event.type === 'year_review') as ReviewEvent | undefined
  // only a review from the month that just ended: an old one is not news on page load
  return review && review.turn >= state.turn - 1 && state.phase !== 'ended' ? review : null
}

export function YearReview({ review, state, onClose }: { review: ReviewEvent; state: GameState; onClose: () => void }) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, SHOW_MS)
    return () => window.clearTimeout(timer)
  }, [review, onClose])

  const year = review.year ?? Math.round(review.turn / 12)
  const years = review.years ?? 3
  const left = years - year
  const nation = review.nation ? state.nations[review.nation] : null
  const approval = review.approval ?? nation?.stats.approval ?? 50
  const mood = approval >= 60 ? 'Soaring' : approval >= THRESHOLD ? 'Solid' : 'Slipping'
  const rows: [string, number | undefined, number | undefined][] = [
    ['Economy', review.gdp, review.gdp_start],
    ['Stability', review.stability, review.stability_start],
  ]

  return (
    <div className="year-review-backdrop" style={theme as CSSProperties} role="dialog" aria-modal="false" aria-labelledby="year-review-heading">
      <article className="year-review" data-mood={mood.toLowerCase()}>
        <p className="election-body">End of year {year} of {years}</p>
        <h2 id="year-review-heading">{nation ? `${nation.leader}: the year in review` : 'The mediator’s year in review'}</h2>
        {nation ? (
          <>
            <div className="year-review-approval">
              <b>{Math.round(approval)}%</b>
              <span>
                approval {review.approval_start != null && <em>{signed.format(approval - review.approval_start)} since taking office</em>}
                <strong>Popularity {mood.toLowerCase()}</strong>
              </span>
            </div>
            <div className="year-review-meter" aria-hidden="true">
              <i style={{ width: `${Math.min(100, Math.max(0, approval))}%` }} />
              <s style={{ left: `${THRESHOLD}%` }} />
            </div>
            <p className="year-review-note">
              {review.election_held ? 'The voters keep you in office. ' : ''}
              {left > 1 ? `${left} years until the final election.` : 'One year left: the final election comes at the end of it.'}
            </p>
            <dl className="year-review-stats">
              {rows.map(([label, now, start]) => now != null && (
                <div key={label}><dt>{label}</dt><dd>{Math.round(now)}{start != null && <small> {signed.format(now - start)}</small>}</dd></div>
              ))}
            </dl>
          </>
        ) : (
          <p className="year-review-note">
            {review.wars ? `${review.wars} war${review.wars === 1 ? '' : 's'} still burning.` : 'The continent is at peace.'}
            {' '}{left > 1 ? `${left} years left in your mandate.` : 'One year left: then the peace committee votes.'}
          </p>
        )}
        <button type="button" onClick={onClose} autoFocus>Continue</button>
      </article>
    </div>
  )
}
