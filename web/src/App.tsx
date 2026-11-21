import { useState, type CSSProperties, type ReactNode } from 'react'
import { CrisisBar, crisisTime } from './CrisisBar'
import { EndScreen } from './EndScreen'
import { Intelligence } from './Intelligence'
import { Phone } from './Phone'
import { ReplayPanel } from './ReplayPanel'
import { WarForecast } from './WarForecast'
import { PoliticalMap } from './PoliticalMap'
import { relationBetween, statLabels, systemLabels, type GameState, type Nation, type Stats } from './state'
import { nationStyle, theme } from './theme'

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
          {resourceKeys.map((key) => (
            <div key={key}>
              <dt>{statLabels[key]}</dt>
              <dd>{seat.stats[key]}</dd>
            </div>
          ))}
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
            <button className="nation-button" data-protests={nation.status.includes('PROTESTS')} onClick={() => onSelect(id)} aria-pressed={id === selected}>
              {nationArtwork[`./nations/${id}-flag.svg`] ? (
                <img className="nation-flag nation-mark" src={nationArtwork[`./nations/${id}-flag.svg`]} alt="" />
              ) : <span className="nation-mark" aria-hidden="true" />}
              <span className="nation-contact">
                <strong>{nation.name}</strong>
                <span>{nation.leader}</span>
              </span>
              {id === state.seat.nation && <span className="seat-label">You</span>}
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

function Dispatches({ news }: { news: GameState['news'] }) {
  return (
    <section className="dispatches" aria-labelledby="dispatches-heading">
      <h2 id="dispatches-heading">The World Dispatch</h2>
      {news.length ? (
        <ol>
          {news.map(({ turn, text }, index) => (
            <li key={`${turn}-${index}`}><span>Month {turn}</span><p>{text}</p></li>
          ))}
        </ol>
      ) : <p>No dispatches yet.</p>}
    </section>
  )
}

export function App({ state, controls, online }: { state: GameState; controls: ReactNode; online: boolean }) {
  const nationIds = Object.keys(state.nations)
  const seat = state.seat.nation
  const firstContact = state.nations.ostrava && seat !== 'ostrava' ? 'ostrava' : nationIds.find((id) => id !== seat)
  const [selection, setSelection] = useState(firstContact ?? nationIds[0])
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
      {state.crisis && <CrisisBar crisis={state.crisis} nations={state.nations} />}
      <main className="theatre">
        <PoliticalMap state={state} selected={selected} onSelect={setSelection} />
        <div className="left-rail">
          <NationRail state={state} selected={selected} onSelect={setSelection} />
          {canReplay && <ReplayPanel nations={state.nations} online={online} />}
          <Dispatches news={news.slice(0, 2)} />
        </div>
        <div className="right-rail">
          <WarForecast forecast={state.last_futures} />
          {nation && (
            <NationDetail nation={nation} id={selected} relation={relation}
              intel={selected !== seat && <Intelligence key={selected} state={state} id={selected} online={online} />} />
          )}
          <Phone state={state} selected={selected} online={online} />
        </div>
      </main>
      <footer className="ticker">
        <strong>Latest dispatch</strong>
        <p>{headline?.text ?? 'No dispatches yet.'}</p>
      </footer>
    </div>
  )
}
