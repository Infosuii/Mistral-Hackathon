import type { CSSProperties } from 'react'
import oneBerth from '../../contracts/examples/crisis_file.one_berth.json'
import type { CrisisState, GameState } from './state'
import { nationStyle } from './theme'

const words = (value: string) => value.replaceAll('_', ' ')

export function crisisTime(tick: number, total: number) {
  const minutes = Math.floor(1440 * tick / total)
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`
}

export function CrisisBar({ crisis, nations, clockHeld }: {
  crisis: CrisisState
  nations: GameState['nations']
  clockHeld: boolean
}) {
  const deadlines = Object.entries(crisis.deadlines).sort(([, a], [, b]) => a - b)
  const progress = `${100 * crisis.tick / crisis.ticks_total}%`
  const name = (id: string) => id === 'player' ? 'You' : nations[id]?.name ?? id

  return (
    <section className="crisis-bar" aria-labelledby="crisis-heading">
      <div className="crisis-timeline">
        <div className="crisis-heading">
          <h2 id="crisis-heading">{crisis.id === oneBerth.id ? oneBerth.title : words(crisis.id)}</h2>
          <span aria-live="polite" data-clock-held={clockHeld}>
            {clockHeld ? 'Clock held: on a call' : `Tick ${crisis.tick} of ${crisis.ticks_total}`}
          </span>
        </div>
        <div className="deadline-track" aria-hidden="true" style={{ '--elapsed': progress } as CSSProperties}>
          {deadlines.map(([id, tick]) => (
            <span key={id} className="deadline-mark" style={{
              ...nationStyle(id), left: `${100 * tick / crisis.ticks_total}%`,
            }} />
          ))}
        </div>
        <ul className="deadline-list" aria-label="National deadlines">
          {deadlines.map(([id, tick]) => {
            const decision = crisis.decisions[id]
            return (
              <li key={id} style={nationStyle(id)} data-decided={Boolean(decision)}>
                <span>{name(id)}</span>
                <time>{crisisTime(tick, crisis.ticks_total)}</time>
                {decision && <small>{words(decision.action)}</small>}
              </li>
            )
          })}
        </ul>
      </div>
      <div className="crisis-ledger">
        <section aria-labelledby="promises-heading">
          <h3 id="promises-heading">Promises</h3>
          {crisis.promises.length ? (
            <ol aria-label="Promises">
              {crisis.promises.map((promise) => (
                <li key={promise.id}>
                  <b>{name(promise.by)} → {name(promise.to)}</b>
                  <p>{words(promise.what)} · {words(promise.when)}{promise.condition && ` · if ${words(promise.condition)}`}</p>
                  {promise.kept !== null && <small>{promise.kept ? 'Kept' : 'Broken'}</small>}
                </li>
              ))}
            </ol>
          ) : <p>None recorded.</p>}
        </section>
        <section aria-labelledby="commitments-heading">
          <h3 id="commitments-heading">Public commitments</h3>
          {crisis.public_commitments.length ? (
            <ol aria-label="Public commitments">
              {crisis.public_commitments.map(({ nation, action, tick }, index) => (
                <li key={`${nation}-${tick}-${index}`}>
                  <b>{name(nation)}</b> {words(action)} · {crisisTime(tick, crisis.ticks_total)}
                </li>
              ))}
            </ol>
          ) : <p>None announced.</p>}
        </section>
      </div>
    </section>
  )
}
