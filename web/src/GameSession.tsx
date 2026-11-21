import { useCallback, useEffect, useRef, useState } from 'react'
import crisisRequest from '../../contracts/examples/crisis_start.request.json'
import startRequest from '../../contracts/examples/start.request.json'
import { api, post } from './api'
import { App } from './App'
import type { PhoneActivity } from './Phone'
import { exampleState, type GameState } from './state'

const pollInterval = 1_000
const turnInterval = 20_000
const crisisInterval = 7_500
const idlePhone: PhoneActivity = { busy: false, waitingForState: false }

function holdClock(state: GameState, phone: PhoneActivity) {
  return Boolean(state.crisis && (phone.busy || phone.waitingForState || state.last_call?.pending))
}

const gameRequests = {
  start: { path: '/start', body: startRequest, error: 'Could not start the game.' },
  turn: { path: '/turn', body: undefined, error: 'Could not advance. Try again.' },
  end: { path: '/end', body: undefined, error: 'Could not end the session.' },
  crisis: { path: '/crisis/start', body: crisisRequest, error: 'Could not start One Berth.' },
}


export function GameSession() {
  const [state, setState] = useState(exampleState)
  const latestState = useRef(exampleState)
  const phone = useRef(idlePhone)
  const [phoneActivity, setPhoneActivity] = useState(idlePhone)
  const [connection, setConnection] = useState<'connecting' | 'online' | 'offline'>('connecting')
  const [newSeat, setNewSeat] = useState<'president' | 'mediator'>('president')
  const [session, setSession] = useState(0)
  const [paused, setPaused] = useState(true)
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

  const send = useCallback(async (action: keyof typeof gameRequests, body?: unknown) => {
    if (actionPending.current || (action === 'turn' && holdClock(latestState.current, phone.current))) return
    actionPending.current = true
    stateRequest.current?.abort()
    setPending(true)
    setError('')
    const request = gameRequests[action]
    try {
      const next = await post<GameState>(request.path, body ?? request.body)
      acceptState(next)
      setConnection('online')
      if (action === 'start') setSession((current) => current + 1)
      if (action === 'end') setPaused(true)
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
    if (canAdvance && !paused && !pending && !clockHeld) {
      const timer = window.setTimeout(() => void send('turn'), crisisTick === undefined ? turnInterval : crisisInterval)
      return () => window.clearTimeout(timer)
    }
  }, [canAdvance, paused, pending, clockHeld, send, state.turn, crisisTick])

  const canMediate = online && state.available_roles?.includes('mediator')
  const startBody = canMediate && newSeat === 'mediator'
    ? { ...startRequest, seat: { role: 'mediator', nation: null } }
    : startRequest
  const controls = (
    <div className="session-controls" aria-label="Session controls">
      {canMediate && (
        <select aria-label="Seat for new game" className="plain-control" value={newSeat}
          onChange={(event) => setNewSeat(event.target.value === 'mediator' ? 'mediator' : 'president')} disabled={pending}>
          <option value="president">President of Valdoria</option>
          <option value="mediator">Independent mediator</option>
        </select>
      )}
      <button onClick={() => void send('start', startBody)} disabled={pending}>{state.phase !== 'ended' && (state.turn === 0 || !online) ? 'Start game' : 'New game'}</button>
      {state.phase !== 'ended' && (
        <>
          <button onClick={() => setPaused((wasPaused) => !wasPaused)} disabled={!canAdvance || pending}>{paused ? 'Resume' : 'Pause'}</button>
          <button onClick={() => void send('turn')} disabled={!canAdvance || pending || clockHeld}>{state.crisis ? 'Next tick' : 'Next turn'}</button>
          {online && state.phase === 'strategy' && (
            <>
              <button onClick={() => void send('crisis')} disabled={pending}>Start One Berth</button>
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

  return <App key={session} state={state} controls={controls} online={online} clockHeld={clockHeld} onPhoneActivity={updatePhone} />
}
