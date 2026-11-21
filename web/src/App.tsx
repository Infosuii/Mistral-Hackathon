import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { CrisisBar, crisisTime } from './CrisisBar'
import { EndScreen } from './EndScreen'
import { Intelligence } from './Intelligence'
import { Phone, type PhoneActivity } from './Phone'
import { ReplayPanel } from './ReplayPanel'
import { WarForecast } from './WarForecast'
import { PoliticalMap } from './PoliticalMap'
import { relationBetween, statLabels, systemLabels, type GameState, type MapEvent, type Nation, type Stats } from './state'
import { nationStyle, theme } from './theme'
import { StatIcon } from './hud/Icons'
import { flagOf, mood, portraitOf } from './hud/MapLayers'
import { Newsboard } from './Newsboard'

const nationArtwork = import.meta.glob<string>('./nations/*.svg', { eager: true, query: '?url', import: 'default' })

const resourceKeys = ['gdp', 'oil', 'food', 'chips', 'army', 'stability', 'approval'] as const
const detailKeys: (keyof Stats)[] = [...resourceKeys, 'territory']
function TurnClock({ state }: { state: GameState }) {
  const crisis = state.phase === 'crisis' ? state.crisis : null
  return (
    <div className="turn-clock">
      <span className="subtle">{crisis ? 'Crisis clock' : state.phase === 'ended' ? 'Session ended' : 'Strategy phase'}</span>
      <strong>{crisis ? crisisTime(crisis.tick, crisis.ticks_total) : `Month ${String(state.turn).padStart(2, '0')}`}</strong>
    </div>
  )
}

function ResourceBar({ state, controls }: { state: GameState; controls: ReactNode }) {
  const seat = state.seat.nation ? state.nations[state.seat.nation] : undefined
  // Month-over-month change: remember the seat's stats the first time each month is seen.
  const seen = useRef(new Map<number, Stats>())
  if (seat && !seen.current.has(state.turn)) seen.current.set(state.turn, { ...seat.stats })
  const before = seen.current.get(state.turn - 1)
  return (
    <header className="topbar">
      <h1 className="wordmark">
        <svg viewBox="0 0 24 24" className="symbol" aria-hidden="true">
          <path d="M12 1 23 12 12 23 1 12Z M12 5v14 M5 12h14" />
        </svg>
        GAMBIT
      </h1>
      <div className="seat" style={nationStyle(state.seat.nation ?? '')}>
        <span className="subtle">{state.seat.role}</span>
        <strong>{seat?.name ?? 'Independent'}</strong>
      </div>
      {seat && (
        <dl className="resources" aria-label={`${seat.name} resources`}>
          {resourceKeys.map((key) => {
            const delta = before ? Math.round((seat.stats[key] - before[key]) * 10) / 10 : 0
            return (
              <div key={key} className="resource" title={statLabels[key]}>
                <dt><StatIcon name={key} />{statLabels[key]}</dt>
                <dd>{Math.round(seat.stats[key] * 10) / 10}</dd>
                {delta !== 0 && <span className="delta" data-sign={Math.sign(delta)}>{delta > 0 ? '▲' : '▼'}{Math.abs(delta)}</span>}
              </div>
            )
          })}
        </dl>
      )}
      {controls}
      <TurnClock state={state} />
    </header>
  )
}

function NationRail({ state, selected, onSelect }: {
  state: GameState
  selected: string | undefined
  onSelect: (id: string) => void
}) {
  return (
    <nav className="panel contacts" aria-labelledby="contacts-heading">
      <h2 className="panel-heading" id="contacts-heading">Nations</h2>
      <ul>
        {Object.entries(state.nations).map(([id, nation]) => (
          <li key={id} style={nationStyle(id)}>
            <button className="nation-button leader-card" data-protests={nation.status.includes('PROTESTS')}
              data-mood={id === state.seat.nation ? 'self' : mood(state, id).tone}
              data-calling={state.incoming_call?.from === id}
              onClick={() => onSelect(id)} aria-pressed={id === selected}>
              <span className="card-portrait">
                {portraitOf(id) ? <img src={portraitOf(id)} alt="" /> : <span className="nation-mark" aria-hidden="true" />}
                {flagOf(id) && <img className="card-flag" src={flagOf(id)} alt="" />}
              </span>
              <span className="nation-contact">
                <strong>{nation.name}</strong>
                <span>{nation.leader}</span>
                {id === state.seat.nation ? <em className="card-mood">Your nation</em> : (
                  <em className="card-mood">
                    {mood(state, id).label}
                    {relationBetween(state, state.seat.nation, id) !== undefined && <b> {new Intl.NumberFormat('en', { signDisplay: 'exceptZero' }).format(relationBetween(state, state.seat.nation, id)!)}</b>}
                    {nation.status.includes('PROTESTS') && <i> · Protests</i>}
                  </em>
                )}
                {nation.beliefs && (
                  <span className="trust-bar" title={`Trust in you ${Math.round(nation.beliefs.trust_in_player * 100)}%`}>
                    <span style={{ width: `${nation.beliefs.trust_in_player * 100}%` }} />
                  </span>
                )}
              </span>
              {state.incoming_call?.from === id && <span className="calling-pill">Calling</span>}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}

function NationDetail({ nation, id, relation, intel }: { nation: Nation; id: string; relation?: number; intel?: ReactNode }) {
  const portrait = nationArtwork[`./nations/${id}-portrait.svg`]
  return (
    <section className="panel dossier" style={nationStyle(id)} aria-labelledby="nation-heading">
      <header className="nation-profile">
        <div>
          <span className="subtle">{systemLabels[nation.system] ?? nation.system}</span>
          <h2 id="nation-heading">{nation.name}</h2>
          <p>{nation.leader}</p>
        </div>
        {portrait && <img className="nation-portrait" src={portrait} alt="" />}
      </header>
      <dl className="nation-stats">
        {detailKeys.map((key) => (
          <div key={key}>
            <dt>{statLabels[key]}</dt>
            <dd>{nation.stats[key]}</dd>
            {(key === 'stability' || key === 'approval') && (
              <meter min={0} max={100} value={nation.stats[key]} aria-label={statLabels[key]} />
            )}
          </div>
        ))}
      </dl>
      {(relation !== undefined || nation.status.length > 0) && (
        <div className="nation-status">
          {relation !== undefined && (
            <span>Relations <b>{new Intl.NumberFormat('en', { signDisplay: 'exceptZero' }).format(relation)}</b></span>
          )}
          {nation.status.map((status) => <strong key={status}>{status}</strong>)}
        </div>
      )}
      {nation.public_statement && (
        <div className="statement">
          <h3>Public statement</h3>
          <blockquote>{nation.public_statement}</blockquote>
        </div>
      )}
      {intel}
    </section>
  )
}

function Dispatches({ news, total, onOpen }: { news: GameState['news']; total: number; onOpen: () => void }) {
  return (
    <section className="dispatches" aria-labelledby="dispatches-heading">
      <button type="button" className="dispatches-open" onClick={onOpen} aria-label="Open the newsboard">
        <h2 id="dispatches-heading">The World Dispatch</h2>
        {news.length ? (
          <ol>
            {news.map(({ turn, text }, index) => (
              <li key={`${turn}-${index}`}><span>Month {turn}</span><p>{text}</p></li>
            ))}
          </ol>
        ) : <p>No dispatches yet.</p>}
        <span className="dispatches-more"><span>Newsboard · {total} stories</span><span aria-hidden="true">N ›</span></span>
      </button>
    </section>
  )
}

export function App({ state, controls, online, clockHeld, historyFocus, onPhoneActivity }: {
  state: GameState
  controls: ReactNode
  online: boolean
  clockHeld: boolean
  historyFocus: MapEvent | null
  onPhoneActivity: (change: Partial<PhoneActivity>) => void
}) {
  const nationIds = Object.keys(state.nations)
  const seat = state.seat.nation
  const [selection, setSelection] = useState(seat ?? nationIds[0])
  const [mapFocus, setMapFocus] = useState<MapEvent | null>(null)
  const [newsOpen, setNewsOpen] = useState(false)
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      if (event.key.toLowerCase() !== 'n' || event.ctrlKey || event.metaKey || event.altKey) return
      if (target && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))) return
      if (document.querySelector('dialog[open]:not(.newsboard)')) return
      setNewsOpen((open) => !open)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => {
    if (historyFocus?.nation) setSelection(historyFocus.nation)
    if (historyFocus) setMapFocus(historyFocus)
  }, [historyFocus])
  const selected = state.nations[selection] ? selection : nationIds[0]
  const nation = state.nations[selected]
  const relation = relationBetween(state, seat, selected)
  const news = [...state.news].reverse()
  const headline = news[0]
  const canReplay = !state.crisis && state.events.some((event) => event.type === 'crisis_resolved')

  if (state.phase === 'ended') {
    return (
      <div className="game-screen" style={theme as CSSProperties}>
        <ResourceBar state={state} controls={controls} />
        <EndScreen state={state} online={online} />
      </div>
    )
  }

  return (
    <div className="game-screen" style={theme as CSSProperties} data-crisis={Boolean(state.crisis)}>
      <ResourceBar state={state} controls={controls} />
      {state.crisis && <CrisisBar
        crisis={state.crisis} nations={state.nations} catalog={state.available_crises} clockHeld={clockHeld}
      />}
      <main className="theatre">
        <PoliticalMap state={state} online={online} historyFocus={mapFocus} selected={selected} onSelect={setSelection} />
        <div className="left-rail">
          <NationRail state={state} selected={selected} onSelect={(id) => {
            setSelection(id)
            setMapFocus({ type: 'focus', turn: state.turn, nation: id })
          }} />
          {canReplay && <ReplayPanel nations={state.nations} online={online} />}
          <Dispatches news={news.slice(0, 1)} total={news.length} onOpen={() => setNewsOpen(true)} />
        </div>
        <div className="right-rail">
          <WarForecast forecast={state.last_futures} />
          {nation && (
            <NationDetail nation={nation} id={selected} relation={relation}
              intel={selected !== seat && state.seat.role !== 'mediator' && <Intelligence key={selected} state={state} id={selected} online={online} />} />
          )}
          <Phone state={state} selected={selected} online={online} onActivity={onPhoneActivity} />
        </div>
      </main>
      <Newsboard state={state} online={online} open={newsOpen} onClose={() => setNewsOpen(false)}
        onLocate={(event) => { if (event.nation) setSelection(event.nation); setMapFocus({ ...event }) }} />
      <footer className="ticker" onClick={() => setNewsOpen(true)} title="Open the newsboard (N)">
        <strong>Live</strong>
        <div className="ticker-track" aria-live="polite">
          <p key={headline?.text}>
            {[0, 1].flatMap((copy) => (news.length ? news.slice(0, 8) : [{ turn: 0, text: 'No dispatches yet.' }]).map(({ turn, text }, i) => (
              <span key={`${copy}-${i}`} aria-hidden={copy === 1}><b>M{turn}</b> {text}</span>
            )))}
          </p>
        </div>
      </footer>
    </div>
  )
}
