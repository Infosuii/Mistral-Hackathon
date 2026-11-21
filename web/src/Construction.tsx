import { useRef, useState, type FormEvent } from 'react'
import buildings from '../../data/buildings.json'
import counties from '../../data/counties.json'
import type { GameState } from './state'

const kinds = buildings.kinds
type Kind = keyof typeof kinds
type Project = { province: string; kind: string }
const countyOf = new Map(counties.flatMap((county) => county.provinces.map((id) => [id, county.name])))
const resources: Record<string, string> = { gdp: 'Economy', food: 'Food', oil: 'Oil', chips: 'Chips', army: 'Army' }

function summary(values: Record<string, number>) {
  return Object.entries(values).map(([resource, value]) => `${value} ${resources[resource]}`).join(' · ')
}

// The server says why a project was refused; show that instead of a generic line.
async function send(path: string, project: Project): Promise<GameState> {
  const response = await fetch(`/api${path}`, {
    method: 'POST',
    signal: AbortSignal.timeout(60_000),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(project),
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = body && typeof body.detail === 'string' ? body.detail : `the server answered ${response.status}`
    throw new Error(detail)
  }
  return body as GameState
}

export function Construction({ state, online, waiting, onQueued }: {
  state: GameState
  online: boolean
  waiting?: boolean
  onQueued: (state: GameState) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [selected, setSelected] = useState('')
  const [kind, setKind] = useState<Kind>('factory')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const player = state.seat.nation
  if (!player) return null
  const nation = state.nations[player]
  const disrupted = new Set(state.disrupted ?? [])
  const queued = state.construction_queue ?? []
  const provinces = Object.keys(state.provinces).filter((id) => state.provinces[id] === player)
  const province = provinces.includes(selected) ? selected : provinces[0]
  const existing = (state.buildings ?? []).filter((building) => building.province === province)
  const queuedHere = queued.filter((project) => project.province === province)
  const taken = [...existing.map((b) => b.kind), ...queuedHere.map((p) => p.kind)]
  const spec = kinds[kind]
  const funds = nation.stats as unknown as Record<string, number>
  const short = Object.entries(spec.cost).filter(([key, price]) => funds[key] < price).map(([key]) => resources[key])
  const unavailable = !online || waiting || state.phase !== 'strategy' || !province
  const blocked = unavailable || busy || short.length > 0 || taken.length >= 3 || taken.includes(kind)

  async function queue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (blocked) return
    setBusy(true)
    setMessage('')
    try {
      onQueued(await send('/construction', { province, kind }))
      setMessage(`${spec.name} paid for; it opens next month.`)
    } catch (error) {
      setMessage(`Could not queue the project: ${error instanceof Error ? error.message : 'unknown error'}.`)
    } finally {
      setBusy(false)
    }
  }

  async function cancel(project: Project) {
    setBusy(true)
    setMessage('')
    try {
      onQueued(await send('/construction/cancel', project))
      setMessage(`${kinds[project.kind as Kind]?.name ?? project.kind} cancelled and refunded.`)
    } catch (error) {
      setMessage(`Could not cancel: ${error instanceof Error ? error.message : 'unknown error'}.`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" onClick={() => { setMessage(''); dialog.current?.showModal() }}>Build</button>
      <dialog className="session-dialog build-dialog" ref={dialog} aria-labelledby="build-title">
        <header>
          <h2 id="build-title">Build in {nation.name}</h2>
          <form method="dialog"><button autoFocus>Close</button></form>
        </header>
        <form onSubmit={queue}>
          <div className="history-views">
            <label>Province
              <select value={province ?? ''} onChange={(event) => setSelected(event.target.value)}>
                {provinces.map((id) => (
                  <option key={id} value={id}>
                    {countyOf.get(id)} · {id.toUpperCase()}{disrupted.has(id) ? ' · disrupted' : ''}
                  </option>
                ))}
              </select>
            </label>
            <label>Facility
              <select value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
                {Object.entries(kinds).map(([id, building]) => (
                  <option key={id} value={id} disabled={taken.includes(id)}>{building.name}</option>
                ))}
              </select>
            </label>
          </div>
          <p><b>Cost</b> {summary(spec.cost)} <small>(paid now, refunded if cancelled)</small></p>
          <p><b>Monthly output</b> +{summary(spec.output)}</p>
          {province && disrupted.has(province) && <p>War has disrupted this province: it produces at half output for now.</p>}
          {existing.length > 0 && <p><b>Built here</b> {existing.map(({ kind }) => kinds[kind as Kind]?.name ?? kind).join(', ')}</p>}
          {queued.length > 0 && (
            <div>
              <b>Opening next month</b>
              <ul>
                {queued.map((project) => (
                  <li key={`${project.province}:${project.kind}`}>
                    {kinds[project.kind as Kind]?.name ?? project.kind} · {countyOf.get(project.province)} {project.province.toUpperCase()}
                    {' '}<button type="button" disabled={unavailable || busy} onClick={() => void cancel(project)}>Cancel</button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {short.length > 0 && <p>Not enough {short.join(', ')}.</p>}
          {taken.includes(kind) && <p>That facility is already built or queued in this province.</p>}
          {!taken.includes(kind) && taken.length >= 3 && <p>This province already has three facilities.</p>}
          {waiting && <p>Wait for the month to finish.</p>}
          {state.phase !== 'strategy' && <p>Construction resumes after the crisis.</p>}
          {message && <p role="status">{message}</p>}
          <button type="submit" disabled={blocked}>Queue construction</button>
        </form>
      </dialog>
    </>
  )
}
