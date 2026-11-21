import { useState, type CSSProperties } from 'react'
import callRequest from '../../contracts/examples/call.request.text.json'
import callResponse from '../../contracts/examples/call.response.json'
import { PoliticalMap } from './PoliticalMap'
import { relationBetween, statLabels, systemLabels, type GameState, type Nation, type Stats } from './state'
import { nationStyle, theme } from './theme'

const nationArtwork = import.meta.glob<string>('./nations/*.svg', { eager: true, query: '?url', import: 'default' })

const resourceKeys = ['gdp', 'oil', 'food', 'chips', 'army', 'stability', 'approval'] as const
const detailKeys: (keyof Stats)[] = [...resourceKeys, 'territory']
function TurnClock({ state }: { state: GameState }) {
  const crisis = state.phase === 'crisis' ? state.crisis : null
  const minutes = crisis?.ticks_total ? Math.floor(1440 * crisis.tick / crisis.ticks_total) : 0
  const pad = (value: number) => String(value).padStart(2, '0')
  const time = `${pad(Math.floor(minutes / 60))}:${pad(minutes % 60)}`
  return (
    <div className="turn-clock">
      <span className="subtle">{crisis ? 'Crisis clock' : state.phase === 'ended' ? 'Session ended' : 'Strategy phase'}</span>
      <strong>{crisis ? time : `Month ${pad(state.turn)}`}</strong>
    </div>
  )
}

function ResourceBar({ state }: { state: GameState }) {
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

function NationDetail({ nation, id, relation }: { nation: Nation; id: string; relation?: number }) {
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
    </section>
  )
}

function Phone({ state, selected }: { state: GameState; selected: string | undefined }) {
  const [showPreview, setShowPreview] = useState(false)
  const incoming = state.incoming_call
  const contactId = incoming?.from ?? selected
  const contact = contactId && contactId !== state.seat.nation ? state.nations[contactId] : undefined
  const canPreview = !incoming && contactId === callRequest.to && Boolean(contact)

  return (
    <section className="panel phone" aria-labelledby="phone-heading">
      <header className="phone-heading">
        <svg className="symbol" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3.5 3h5l2.1 5.3-3 1.8a15.5 15.5 0 0 0 6.3 6.3l1.8-3L21 15.5v5l-1 .5C10.6 21 3 13.4 3 4Z" />
        </svg>
        <h2 id="phone-heading">Red Phone</h2>
      </header>
      <div className="phone-line" aria-live="polite">
        <span className="subtle">{incoming ? 'Incoming call' : contact ? 'Direct line' : 'Select a foreign leader'}</span>
        {contact && <strong>{contact.leader}</strong>}
        {incoming?.opening_line && <p>{incoming.opening_line}</p>}
        {canPreview && showPreview && (
          <div className="transcript">
            <p><b>You</b> {callResponse.transcript}</p>
            <p><b>{contact?.name}</b> {callResponse.reply_text}</p>
          </div>
        )}
      </div>
      <div id="phone-controls">
        {canPreview ? (
          <button className="preview-call" onClick={() => setShowPreview((visible) => !visible)} aria-expanded={showPreview}>
            {showPreview ? 'Close preview' : 'Preview call'}
          </button>
        ) : <p className="subtle phone-offline">Voice offline</p>}
      </div>
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

export function App({ state }: { state: GameState }) {
  const nationIds = Object.keys(state.nations)
  const seat = state.seat.nation
  const firstContact = state.nations.ostrava && seat !== 'ostrava' ? 'ostrava' : nationIds.find((id) => id !== seat)
  const [selection, setSelection] = useState(firstContact ?? nationIds[0])
  const selected = state.nations[selection] ? selection : nationIds[0]
  const nation = state.nations[selected]
  const relation = relationBetween(state, seat, selected)
  const news = [...state.news].reverse()
  const headline = news[0]

  return (
    <div className="game-screen" style={theme as CSSProperties}>
      <ResourceBar state={state} />
      <main className="theatre">
        <PoliticalMap state={state} selected={selected} onSelect={setSelection} />
        <div className="left-rail">
          <NationRail state={state} selected={selected} onSelect={setSelection} />
          <Dispatches news={news.slice(0, 2)} />
        </div>
        <div className="right-rail">
          {nation && <NationDetail nation={nation} id={selected} relation={relation} />}
          <Phone key={selected} state={state} selected={selected} />
        </div>
      </main>
      <footer className="ticker">
        <strong>Latest dispatch</strong>
        <p>{headline?.text ?? 'No dispatches yet.'}</p>
      </footer>
    </div>
  )
}
