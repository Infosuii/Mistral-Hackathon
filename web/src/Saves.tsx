import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api, post } from './api'
import type { GameState } from './state'

export interface SaveSlot {
  id: string
  name: string
  seed: number
  nation: string | null
  turn: number
  saved_at: string
}

export function Saves({ state, disabled, onOpen, onLoad }: {
  state: GameState
  disabled: boolean
  onOpen: () => void
  onLoad: (slot: SaveSlot) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [slots, setSlots] = useState<SaveSlot[]>([])
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    setName(`Seed ${state.seed} · Month ${state.turn}`)
  }, [state.seed, state.turn])

  async function open() {
    onOpen()
    dialog.current?.showModal()
    setBusy(true)
    setMessage('')
    try {
      setSlots(await api<SaveSlot[]>('/saves', { cache: 'no-store' }))
    } catch {
      setMessage('Could not list saves. Check the game connection.')
    } finally {
      setBusy(false)
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!name.trim() || disabled || busy) return
    setBusy(true)
    try {
      const slot = await post<SaveSlot>('/saves', { name: name.trim() })
      setSlots((current) => [slot, ...current])
      setMessage(`Saved ${slot.name}.`)
    } catch {
      setMessage('Save failed. The current game is still open.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" disabled={disabled} onClick={() => void open()}>Saves</button>
      <dialog className="session-dialog history-dialog" ref={dialog} aria-labelledby="saves-title">
        <header>
          <h2 id="saves-title">Saved worlds</h2>
          <form method="dialog"><button autoFocus>Close</button></form>
        </header>
        <form onSubmit={save} className="save-form">
          <label>Save name<input value={name} maxLength={80} required onChange={(event) => setName(event.target.value)} /></label>
          <button type="submit" disabled={disabled || busy}>Save current world</button>
        </form>
        <p role="status">{message}</p>
        <ul className="save-slots">
          {!slots.length && !busy && <li>No saved worlds yet.</li>}
          {slots.map((slot) => (
            <li key={slot.id}>
              <div>
                <strong>{slot.name}</strong>
                <small>
                  Seed {slot.seed} · {slot.nation ? state.nations[slot.nation]?.name ?? slot.nation : 'Mediator'} · Month {slot.turn}
                </small>
                <small>{new Date(slot.saved_at).toLocaleString()}</small>
              </div>
              <button type="button" disabled={disabled || busy} onClick={() => {
                if (!window.confirm(`Load ${slot.name}? This replaces the current session.`)) return
                dialog.current?.close()
                onLoad(slot)
              }}>Load</button>
            </li>
          ))}
        </ul>
      </dialog>
    </>
  )
}
