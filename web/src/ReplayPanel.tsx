import { useState, type FormEvent } from 'react'
import { post } from './api'
import type { GameState } from './state'

interface ReplayResult {
  shift_ticks: number
  changed: { nation: string; was: string; now: string; why: string }[]
}

function describeShift(ticks: number) {
  if (ticks === 0) return 'Original timing'
  const count = Math.abs(ticks)
  return `${count} ${count === 1 ? 'tick' : 'ticks'} ${ticks < 0 ? 'earlier' : 'later'}`
}

export function ReplayPanel({ nations, online }: { nations: GameState['nations']; online: boolean }) {
  const [shift, setShift] = useState(3)
  const [result, setResult] = useState<ReplayResult>()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(false)

  async function run(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy || !online) return
    setBusy(true)
    setError(false)
    setResult(undefined)
    try {
      setResult(await post<ReplayResult>('/replay', { shift_ticks: shift }))
    } catch {
      setError(true)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel replay-panel" aria-labelledby="replay-heading">
      <h2 id="replay-heading">What if I’d waited?</h2>
      <form onSubmit={run}>
        <label htmlFor="replay-shift">Call timing</label>
        <output htmlFor="replay-shift">{describeShift(shift)}</output>
        <input id="replay-shift" type="range" min="-4" max="4" step="1" value={shift}
          aria-valuetext={describeShift(shift)} disabled={busy}
          onChange={(event) => { setShift(event.target.valueAsNumber); setResult(undefined); setError(false) }} />
        <button className="plain-control" disabled={busy || !online}>{busy ? 'Replaying' : 'Run replay'}</button>
      </form>
      <div className="replay-result" aria-live="polite">
        {error && <p className="call-error">Could not replay this crisis. Try again.</p>}
        {result && (result.changed.length ? (
          <ul>
            {result.changed.map(({ nation, was, now, why }) => (
              <li key={nation}>
                <b>{nations[nation]?.name ?? nation}</b>
                <p>{was.replaceAll('_', ' ')} → {now.replaceAll('_', ' ')}</p>
                <p>{why}</p>
              </li>
            ))}
          </ul>
        ) : <p>No leader changed their decision.</p>)}
      </div>
    </section>
  )
}
