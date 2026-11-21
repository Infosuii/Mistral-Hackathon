import { useRef, useState, type FormEvent } from 'react'
import buildings from '../../data/buildings.json'
import counties from '../../data/counties.json'
import { post } from './api'
import type { GameState } from './state'

const kinds = buildings.kinds
type Kind = keyof typeof kinds
const countyOf = new Map(counties.flatMap((county) => county.provinces.map((id) => [id, county.name])))
const resources: Record<string, string> = { gdp: 'Economy', food: 'Food', oil: 'Oil', chips: 'Chips', army: 'Army' }

function summary(values: Record<string, number>) {
  return Object.entries(values).map(([resource, value]) => `${value} ${resources[resource]}`).join(' · ')
}

export function Construction({ state, online, onQueued }: {
  state: GameState
  online: boolean
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
  const provinces = Object.keys(state.provinces).filter((id) => state.provinces[id] === player)
  const province = provinces.includes(selected) ? selected : provinces[0]
  const existing = (state.buildings ?? []).filter((building) => building.province === province)
  const spec = kinds[kind]
  const funds = nation.stats as unknown as Record<string, number>
  const canAfford = Object.entries(spec.cost).every(([key, price]) => funds[key] >= price)
  const unavailable = !online || state.phase !== 'strategy' || !province

  async function queue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (unavailable || busy || !canAfford) return
    setBusy(true)
    setMessage('')
    try {
      onQueued(await post<GameState>('/construction', { province, kind }))
      setMessage(`${spec.name} queued for next month.`)
    } catch {
      setMessage('Could not queue the project. Check control of the province and available resources.')
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
                {provinces.map((id) => <option key={id} value={id}>{countyOf.get(id)} · {id.toUpperCase()}</option>)}
              </select>
            </label>
            <label>Facility
              <select value={kind} onChange={(event) => setKind(event.target.value as Kind)}>
                {Object.entries(kinds).map(([id, building]) => <option key={id} value={id}>{building.name}</option>)}
              </select>
            </label>
          </div>
          <p><b>Cost</b> {summary(spec.cost)}</p>
          <p><b>Monthly output</b> +{summary(spec.output)}</p>
          {existing.length > 0 && <p><b>Built here</b> {existing.map(({ kind }) => kinds[kind as Kind]?.name ?? kind).join(', ')}</p>}
          {state.construction && <p><b>Next month</b> {kinds[state.construction.kind as Kind]?.name} · {state.construction.province.toUpperCase()}</p>}
          {!canAfford && <p>Insufficient resources.</p>}
          {state.phase !== 'strategy' && <p>Construction resumes after the crisis.</p>}
          {message && <p role="status">{message}</p>}
          <button type="submit" disabled={unavailable || busy || !canAfford || existing.length >= 3 ||
            existing.some((building) => building.kind === kind)}>
            {state.construction ? 'Replace queued project' : 'Queue construction'}
          </button>
        </form>
      </dialog>
    </>
  )
}
