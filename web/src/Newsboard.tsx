import { useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { api } from './api'
import type { GameState, MapEvent } from './state'
import { nationStyle } from './theme'
import './newsboard.css'

type Category = 'war' | 'diplomacy' | 'military' | 'politics' | 'economy' | 'crisis' | 'world'
const categories: Record<Category, { label: string; icon: string }> = {
  war: { label: 'War', icon: '⚔' },
  diplomacy: { label: 'Diplomacy', icon: '✦' },
  military: { label: 'Military', icon: '⛨' },
  politics: { label: 'Politics', icon: '⚑' },
  economy: { label: 'Economy', icon: '◈' },
  crisis: { label: 'Crisis', icon: '◉' },
  world: { label: 'World', icon: '•' },
}

const rules: [Category, RegExp][] = [
  ['war', /\bwar\b|declares|invad|captur|seiz|front|takes .* province|attack/i],
  ['military', /fleet|blockade|army|navy|troops|tugs|patrol|withdraw/i],
  ['crisis', /crisis|berth|grain|fever|deadline|tick|ultimatum/i],
  ['politics', /election|coup|protest|ousted|takes office|leader|stability|strike|riot|unrest|scandal|resign/i],
  ['diplomacy', /trade|alliance|ally|tariff|peace|treaty|rejects|sign|agreement|call/i],
  ['economy', /construct|built|factory|farm|freight|rail|economy|gdp|oil|chips|food/i],
]
const typeCategory: Record<string, Category> = {
  war: 'war', province_taken: 'war', peace: 'diplomacy', trade_deal: 'diplomacy', trade_rejected: 'diplomacy',
  alliance: 'diplomacy', alliance_rejected: 'diplomacy', alliance_left: 'diplomacy', tariff: 'diplomacy',
  election: 'politics', coup: 'politics', fleet_deployed: 'military', fleet_recalled: 'military', fleet_returned: 'military',
  blockade_started: 'military', blockade_lifted: 'military', construction_completed: 'economy', construction_cancelled: 'economy',
}
const categorise = (text: string): Category => rules.find(([, pattern]) => pattern.test(text))?.[0] ?? 'world'

type Entry = { turn: number; text: string; category: Category; event?: MapEvent; nations: string[] }

function useLog(open: boolean, online: boolean, state: GameState) {
  const [log, setLog] = useState<{ news: MapEvent[]; history: MapEvent[] } | null>(null)
  useEffect(() => {
    if (!open || !online) return
    const request = new AbortController()
    Promise.all([
      api<MapEvent[]>('/news', { signal: request.signal, cache: 'no-store' }),
      api<MapEvent[]>('/history', { signal: request.signal, cache: 'no-store' }),
    ]).then(([news, history]) => { if (!request.signal.aborted) setLog({ news, history }) })
      .catch(() => { if (!request.signal.aborted) setLog(null) })
    return () => request.abort()
  }, [open, online, state.turn, state.crisis?.tick, state.news.length])
  return log ?? { news: state.news.map((n) => ({ ...n, type: 'news' })), history: state.events }
}

/** What is true right now, read straight off the state. */
function Situation({ state }: { state: GameState }) {
  const name = (id: string) => state.nations[id]?.name ?? id
  const links = (type: string) => state.links.filter((link) => link.type === type)
  const wars = links('war'), alliances = links('alliance'), trade = links('trade')
  const protests = Object.entries(state.nations).filter(([, n]) => n.status.includes('PROTESTS'))
  const fleets = Object.entries(state.fleets ?? {})
  const seat = state.seat.nation
  const flows = seat ? [
    ['Rail', state.rail_income?.[seat]], ['Roads', state.road_income?.[seat]], ['Air', state.air_income?.[seat]],
  ] as const : []
  const Pair = ({ a, b }: { a: string; b: string }) => <span className="nb-pair">
    <b style={nationStyle(a) as CSSProperties}>{name(a)}</b><i>·</i><b style={nationStyle(b) as CSSProperties}>{name(b)}</b>
  </span>
  return <section className="nb-now" aria-labelledby="nb-now-title">
    <h3 id="nb-now-title">What’s happening now <small>Month {state.turn}{state.crisis ? ` · ${state.crisis.id.replaceAll('_', ' ')} hour ${state.crisis.tick}` : ''}</small></h3>
    <div className="nb-cards">
      <article data-tone="war"><h4>⚔ Wars</h4>{wars.length ? wars.map((l) => <Pair key={l.a + l.b} {...l} />) : <p>The continent is at peace.</p>}</article>
      <article data-tone="diplomacy"><h4>✦ Alliances</h4>{alliances.length ? alliances.map((l) => <Pair key={l.a + l.b} {...l} />) : <p>No standing alliances.</p>}</article>
      <article data-tone="economy"><h4>◈ Trade agreements</h4>{trade.length ? trade.map((l) => <Pair key={l.a + l.b} {...l} />) : <p>No trade agreements.</p>}</article>
      <article data-tone="military"><h4>⛨ Fleets at sea</h4>{fleets.length ? fleets.map(([n, f]) =>
        <p key={n}><b style={nationStyle(n) as CSSProperties}>{name(n)}</b> {f.returning ? 'returning from' : state.turn >= f.arrival_turn ? 'blockading' : 'sailing on'} {name(f.target)}</p>)
        : <p>All fleets in port.</p>}</article>
      <article data-tone="politics"><h4>⚑ Home fronts</h4>{protests.length ? protests.map(([id, n]) =>
        <p key={id}><b style={nationStyle(id) as CSSProperties}>{n.name}</b> protests · stability {Math.round(n.stats.stability)}</p>)
        : <p>No nation faces protests.</p>}</article>
      <article data-tone="economy"><h4>◈ Your logistics</h4>
        <p>{state.rail_services?.length ?? 0} rail · {state.road_services?.length ?? 0} haulage roads · {state.air_services?.length ?? 0} air routes</p>
        {flows.map(([label, income]) => income && Object.keys(income).length
          ? <p key={label}>{label}: {Object.entries(income).map(([k, v]) => `+${v} ${k}`).join(', ')}/mo</p> : null)}
        {state.construction && <p>Building {state.construction.kind.replaceAll('_', ' ')} in {state.construction.province.toUpperCase()}</p>}
      </article>
    </div>
  </section>
}

export function Newsboard({ state, online, open, onClose, onLocate }: {
  state: GameState; online: boolean; open: boolean; onClose: () => void; onLocate: (event: MapEvent) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [filter, setFilter] = useState<Category | 'all'>('all')
  const [query, setQuery] = useState('')
  const log = useLog(open, online, state)

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (open && !element.open) element.showModal()
    if (!open && element.open) element.close()
  }, [open])

  const entries = useMemo(() => {
    const names = Object.entries(state.nations)
    const used = new Set<MapEvent>()
    return log.news.filter((item) => item.text).map((item): Entry => {
      const text = item.text!
      const nations = names.filter(([, n]) => text.includes(n.name)).map(([id]) => id)
      const event = log.history.find((e) => !used.has(e) && e.turn === item.turn && e.nation && nations.includes(e.nation)
        && (typeCategory[e.type] ?? categorise(text)) === categorise(text))
      if (event) used.add(event)
      return { turn: item.turn, text, nations, event, category: event ? typeCategory[event.type] ?? categorise(text) : categorise(text) }
    }).reverse()
  }, [log, state.nations])

  const shown = entries.filter((e) => (filter === 'all' || e.category === filter)
    && (!query || e.text.toLowerCase().includes(query.toLowerCase())))
  const months = new Map<number, Entry[]>()
  for (const entry of shown) months.set(entry.turn, [...(months.get(entry.turn) ?? []), entry])
  const counts = Object.fromEntries((Object.keys(categories) as Category[]).map((c) => [c, entries.filter((e) => e.category === c).length]))

  return <dialog className="newsboard" ref={dialog} onClose={onClose} aria-labelledby="newsboard-title">
    <header className="nb-masthead">
      <div>
        <span className="nb-kicker">Month {state.turn} · {entries.length} dispatches since the campaign began</span>
        <h2 id="newsboard-title">The World Dispatch</h2>
      </div>
      <form method="dialog"><button className="nb-close" aria-label="Close newsboard">×</button></form>
    </header>
    <div className="nb-body">
      <Situation state={state} />
      <section className="nb-timeline" aria-labelledby="nb-timeline-title">
        <div className="nb-toolbar">
          <h3 id="nb-timeline-title">Timeline</h3>
          <input type="search" placeholder="Search dispatches" aria-label="Search dispatches" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="nb-filters" role="group" aria-label="Filter timeline">
          <button type="button" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>All <b>{entries.length}</b></button>
          {(Object.keys(categories) as Category[]).filter((c) => counts[c]).map((c) => (
            <button key={c} type="button" data-tone={c} aria-pressed={filter === c} onClick={() => setFilter(c)}>
              {categories[c].icon} {categories[c].label} <b>{counts[c]}</b>
            </button>
          ))}
        </div>
        <ol className="nb-months">
          {[...months].map(([turn, items]) => (
            <li key={turn} className="nb-month">
              <h4><span>Month {turn}</span>{turn === state.turn && <em>Latest</em>}</h4>
              <ol>
                {items.map((entry, i) => {
                  const target = entry.event ?? (entry.nations[0] ? { type: 'focus', turn: entry.turn, nation: entry.nations[0] } : undefined)
                  return <li key={i} data-tone={entry.category}>
                    <button type="button" disabled={!target} onClick={() => { if (target) { onLocate(target); onClose() } }}
                      title={target ? 'Show on map' : undefined}>
                      <span className="nb-icon" aria-hidden="true">{categories[entry.category].icon}</span>
                      <span className="nb-text">{entry.text}</span>
                      {entry.nations.length > 0 && <span className="nb-chips">{entry.nations.slice(0, 3).map((id) =>
                        <i key={id} style={nationStyle(id) as CSSProperties}>{state.nations[id]?.name}</i>)}</span>}
                    </button>
                  </li>
                })}
              </ol>
            </li>
          ))}
          {!shown.length && <li className="nb-empty">No dispatches match.</li>}
        </ol>
      </section>
    </div>
  </dialog>
}
