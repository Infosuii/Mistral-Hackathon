import { useCallback, useEffect, useRef, useState } from 'react'
import crisisRequest from '../../contracts/examples/crisis_start.request.json'
import startRequest from '../../contracts/examples/start.request.json'
import { api, post } from './api'
import { App } from './App'
import { exampleState, type GameState } from './state'

const pollInterval = 1_000
const turnInterval = 20_000
const crisisInterval = 7_500

const gameRequests = {
  start: { path: '/start', body: startRequest, error: 'Could not start the game.' },
  turn: { path: '/turn', body: undefined, error: 'Could not advance. Try again.' },
  crisis: { path: '/crisis/start', body: crisisRequest, error: 'Could not start One Berth.' },
}


export function GameSession() {
  const [state, setState] = useState(exampleState)
  const [connection, setConnection] = useState<'connecting' | 'online' | 'offline'>('connecting')
  const [paused, setPaused] = useState(true)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const actionPending = useRef(false)
  const stateRequest = useRef<AbortController | null>(null)

  useEffect(() => {
    async function poll() {
      if (actionPending.current || stateRequest.current) return
      const controller = new AbortController()
      stateRequest.current = controller
      const timeout = window.setTimeout(() => controller.abort('timeout'), 4_000)
      try {
        const next = await api<GameState>('/state', { signal: controller.signal, cache: 'no-store' })
        if (!controller.signal.aborted) {
          setState(next)
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
  }, [])

  const send = useCallback(async (action: keyof typeof gameRequests) => {
    if (actionPending.current) return
    actionPending.current = true
    stateRequest.current?.abort()
    setPending(true)
    setError('')
    const request = gameRequests[action]
    try {
      const next = await post<GameState>(request.path, request.body)
      setState(next)
      setConnection('online')
      if (action !== 'turn') setPaused(false)
    } catch {
      setError(request.error)
      setPaused(true)
    } finally {
      actionPending.current = false
      setPending(false)
    }
  }, [])

  const online = connection === 'online'
  const canAdvance = online && state.phase !== 'ended'

  const crisisTick = state.crisis?.tick
  useEffect(() => {
    if (canAdvance && !paused && !pending) {
      const timer = window.setTimeout(() => void send('turn'), crisisTick === undefined ? turnInterval : crisisInterval)
      return () => window.clearTimeout(timer)
    }
  }, [canAdvance, paused, pending, send, state.turn, crisisTick])

  const controls = (
    <div className="session-controls" aria-label="Session controls">
      <button onClick={() => void send('start')} disabled={pending}>{state.turn === 0 || !online ? 'Start game' : 'New game'}</button>
      <button onClick={() => setPaused((wasPaused) => !wasPaused)} disabled={!canAdvance || pending}>{paused ? 'Resume' : 'Pause'}</button>
      <button onClick={() => void send('turn')} disabled={!canAdvance || pending}>{state.crisis ? 'Next tick' : 'Next turn'}</button>
      {online && state.phase === 'strategy' && (
        <button onClick={() => void send('crisis')} disabled={pending}>Start One Berth</button>
      )}
      {connection !== 'online' && <span className="session-status" role="status">{connection === 'connecting' ? 'Connecting' : 'Engine offline'}</span>}
      {pending && <span className="session-status" role="status">Updating world</span>}
      {error && <span className="session-error" role="alert">{error}</span>}
    </div>
  )

  return <App state={state} controls={controls} online={online} />
}
