import { useCallback, useEffect, type FormEvent, useRef, useState } from 'react'
import startRequest from '../../contracts/examples/start.request.json'
import { api, post } from './api'
import { App } from './App'
import { Construction } from './Construction'
import { History } from './History'
import { Saves, type SaveSlot } from './Saves'
import './session-navigation.css'
import type { PhoneActivity } from './Phone'
import { defaultCrisis, exampleState, type GameState, type MapEvent } from './state'

const pollInterval = 1_000
const turnInterval = 20_000
const crisisInterval = 7_500
const idlePhone: PhoneActivity = { busy: false, waitingForState: false }

function holdClock(state: GameState, phone: PhoneActivity) {
  return phone.busy || phone.waitingForState || Boolean(state.last_call?.pending)
}

const gameRequests = {
  load: { path: '/saves', body: undefined, error: 'Could not load the save.' },
  start: { path: '/start', body: startRequest, error: 'Could not start the game.' },
  turn: { path: '/turn', body: undefined, error: 'Could not advance. Try again.' },
  end: { path: '/end', body: undefined, error: 'Could not end the session.' },
  crisis: { path: '/crisis/start', body: undefined, error: 'Could not start the crisis.' },
}


export function GameSession() {
  const [state, setState] = useState(exampleState)
  const latestState = useRef(exampleState)
  const phone = useRef(idlePhone)
  const [phoneActivity, setPhoneActivity] = useState(idlePhone)
  const [connection, setConnection] = useState<'connecting' | 'online' | 'offline'>('connecting')
  const [newCrisis, setNewCrisis] = useState(defaultCrisis.id)
  const [newSeat, setNewSeat] = useState<'president' | 'mediator'>('president')
  const [session, setSession] = useState(0)
  const [historyFocus, setHistoryFocus] = useState<MapEvent | null>(null)
  const [paused, setPaused] = useState(true)
  const [speed, setSpeed] = useState(0.5)
  const [seedDraft, setSeedDraft] = useState(String(startRequest.seed))
  const newWorld = useRef<HTMLDialogElement>(null)
  const [changingSeed, setChangingSeed] = useState(false)
  const [savingSeed, setSavingSeed] = useState(false)
  const seedSaveInProgress = useRef(false)
  const [seedError, setSeedError] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const actionPending = useRef(false)
  const stateRequest = useRef<AbortController | null>(null)

  const updatePhone = useCallback((change: Partial<PhoneActivity>) => {
    if (change.waitingForState) {
      // The reply is pending on the server. A poll already in flight may predate it.
      stateRequest.current?.abort()
    }
    const next = { ...phone.current, ...change }
    if (next.busy === phone.current.busy && next.waitingForState === phone.current.waitingForState) return
    phone.current = next
    setPhoneActivity(next)
  }, [])

  const acceptState = useCallback((snapshot: GameState) => {
    latestState.current = snapshot
    setState(snapshot)
    updatePhone({ waitingForState: false })
  }, [updatePhone])

  useEffect(() => {
    async function poll() {
      if (actionPending.current || stateRequest.current) return
      const controller = new AbortController()
      stateRequest.current = controller
      const timeout = window.setTimeout(() => controller.abort('timeout'), 4_000)
      try {
        const next = await api<GameState>('/state', { signal: controller.signal, cache: 'no-store' })
        if (!controller.signal.aborted) {
          acceptState(next)
          setConnection('online')
        }
      } catch {
        if (!controller.signal.aborted || controller.signal.reason === 'timeout') setConnection('offline')
      } finally {
        window.clearTimeout(timeout)
        if (stateRequest.current === controller) stateRequest.current = null
      }
    }
    void poll()
    const timer = window.setInterval(poll, pollInterval)
    return () => {
      window.clearInterval(timer)
      stateRequest.current?.abort()
    }
  }, [acceptState])

  const send = useCallback(async (action: keyof typeof gameRequests, body?: unknown, slot?: string) => {
    if (actionPending.current || (action === 'turn' && holdClock(latestState.current, phone.current))) return
    actionPending.current = true
    stateRequest.current?.abort()
    setPending(true)
    setError('')
    const request = gameRequests[action]
    try {
      const next = await post<GameState>(action === 'load' ? `/saves/${slot}/load` : request.path, body ?? request.body)
      acceptState(next)
      setConnection('online')
      if (action === 'start' || action === 'load') {
        setSession((current) => current + 1)
        setHistoryFocus(null)
      }
      if (action === 'start' || action === 'load' || action === 'end') setPaused(true)
      else if (action !== 'turn') setPaused(false)
    } catch {
      setError(request.error)
      setPaused(true)
    } finally {
      actionPending.current = false
      setPending(false)
    }
  }, [acceptState])

  const online = connection === 'online'
  const canAdvance = online && state.phase !== 'ended'

  const crisisTick = state.crisis?.tick
  const clockHeld = holdClock(state, phoneActivity)
  useEffect(() => {
    if (canAdvance && !paused && !pending && !clockHeld && !changingSeed) {
      const timer = window.setTimeout(() => void send('turn'), (crisisTick === undefined ? turnInterval : crisisInterval) / speed)
      return () => window.clearTimeout(timer)
    }
  }, [canAdvance, paused, pending, clockHeld, send, state.turn, crisisTick, speed, changingSeed])

  const canMediate = online && state.available_roles?.includes('mediator')
  const startBody = canMediate && newSeat === 'mediator'
    ? { ...startRequest, seat: { role: 'mediator', nation: null } }
    : startRequest
  const crisisOptions = state.available_crises?.length ? state.available_crises : [defaultCrisis]
  const selectedCrisis = crisisOptions.find((scenario) => scenario.id === newCrisis) ?? crisisOptions[0]
  function openNewWorld() {
    setSeedDraft(String(crypto.getRandomValues(new Uint32Array(1))[0]))
    setSeedError('')
    setChangingSeed(true)
    newWorld.current?.showModal()
  }

  async function replaceWorld(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!/^\d+$/.test(seedDraft) || Number(seedDraft) > 4294967295 || pending || clockHeld || seedSaveInProgress.current) return
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null
    if (submitter?.value === 'save') {
      seedSaveInProgress.current = true
      setSavingSeed(true)
      setSeedError('')
      try {
        await post<SaveSlot>('/saves', { name: `Seed ${state.seed} · Month ${state.turn}` })
      } catch {
        setSeedError('Save failed. The current world is still open.')
        return
      } finally {
        seedSaveInProgress.current = false
        setSavingSeed(false)
      }
    }
    newWorld.current?.close()
    void send('start', { ...startBody, seed: Number(seedDraft) })
  }

  const controls = (
    <div className="session-controls" aria-label="Session controls">
      {canMediate && (
        <select aria-label="Seat for new game" className="plain-control" value={newSeat}
          onChange={(event) => setNewSeat(event.target.value === 'mediator' ? 'mediator' : 'president')} disabled={pending}>
          <option value="president">President of Valdoria</option>
          <option value="mediator">Independent mediator</option>
        </select>
      )}
      <button onClick={openNewWorld} disabled={!online || pending || clockHeld}>New Seed</button>
      <dialog className="session-dialog" ref={newWorld} aria-labelledby="new-world-title" onClose={() => setChangingSeed(false)}
        onCancel={(event) => { if (seedSaveInProgress.current) event.preventDefault() }}>
        <form onSubmit={replaceWorld}>
          <h2 id="new-world-title">Start a new world?</h2>
          <p>This replaces the current session for seed {state.seed}.</p>
          <label>World seed
            <input required type="number" min={0} max={4294967295} step={1}
              value={seedDraft} onChange={(event) => setSeedDraft(event.target.value)} />
          </label>
          {seedError && <p role="alert">{seedError}</p>}
          <div className="dialog-actions">
            <button type="button" disabled={savingSeed} autoFocus onClick={() => newWorld.current?.close()}>Cancel</button>
            <button type="submit" disabled={savingSeed}>Start new world</button>
            <button type="submit" value="save" disabled={savingSeed}>{savingSeed ? 'Saving…' : 'Save and start'}</button>
          </div>
        </form>
      </dialog>
      <Saves state={state} disabled={!online || pending || clockHeld} onOpen={() => setPaused(true)}
        onLoad={(slot) => void send('load', undefined, slot.id)} />
      <Construction state={state} online={online} onQueued={(snapshot) => {
        stateRequest.current?.abort()
        acceptState(snapshot)
      }} />
      <History state={state} online={online} onLocate={(event) => setHistoryFocus({ ...event })} />
      {state.phase !== 'ended' && (
        <>
          <button onClick={() => setPaused((wasPaused) => !wasPaused)} disabled={!canAdvance || pending}>{paused ? 'Resume' : 'Pause'}</button>
          <label className="speed-control">
            <span>Speed <output>{speed}×</output></span>
            <input type="range" aria-label="Game speed" min={0.25} max={2} step={0.25}
              value={speed} onChange={(event) => setSpeed(Number(event.target.value))} />
          </label>
          <button onClick={() => void send('turn')} disabled={!canAdvance || pending || clockHeld}>{state.crisis ? 'Next tick' : 'Next turn'}</button>
          {online && state.phase === 'strategy' && (
            <>
              {crisisOptions.length > 1 && (
                <select aria-label="Crisis scenario" className="plain-control" value={selectedCrisis.id}
                  onChange={(event) => setNewCrisis(event.target.value)} disabled={pending}>
                  {crisisOptions.map(({ id, title }) => <option key={id} value={id}>{title}</option>)}
                </select>
              )}
              <button onClick={() => void send('crisis', { id: selectedCrisis.id })} disabled={pending}>
                Start {selectedCrisis.title}
              </button>
              {state.ending !== undefined && <button onClick={() => void send('end')} disabled={pending}>End session</button>}
            </>
          )}
        </>
      )}
      {connection !== 'online' && <span className="session-status" role="status">{connection === 'connecting' ? 'Connecting' : 'Engine offline'}</span>}
      {pending && <span className="session-status" role="status">Updating world</span>}
      {error && <span className="session-error" role="alert">{error}</span>}
    </div>
  )

  return <App key={session} state={state} historyFocus={historyFocus} controls={controls} online={online} clockHeld={clockHeld} onPhoneActivity={updatePhone} />
}
