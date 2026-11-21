// Floating orders bar for the selected nation, at the bottom of the map: who they are,
// how they feel about you, and what you can do now (call, intel, wiretap, plus Om's
// diplomacy actions when web/src/Diplomacy.tsx exists). The bar only renders and
// forwards clicks: the page still computes no game logic.
import type { ComponentType, CSSProperties } from 'react'
import { relationBetween, systemLabels, type GameState } from '../state'
import { nationStyle } from '../theme'
import { mood, portraitOf } from './MapLayers'

// Om's panel, picked up automatically once the file lands on main.
type DiplomacyProps = { state: GameState; target: string }
const modules = import.meta.glob<{ Diplomacy?: ComponentType<DiplomacyProps> }>('../Diplomacy.tsx', { eager: true })
const Diplomacy = Object.values(modules)[0]?.Diplomacy

function openCall() {
  const phone = document.querySelector<HTMLElement>('.phone')
  phone?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  phone?.querySelector<HTMLElement>('input[type="text"], input:not([type]), textarea')?.focus()
  phone?.animate([{ boxShadow: '0 0 0 0 #ff978c' }, { boxShadow: '0 0 0 6px #ff978c00' }], { duration: 700 })
}

function openDossierTab(label: 'Intel' | 'Wiretap') {
  const button = [...document.querySelectorAll<HTMLButtonElement>('.intelligence-controls button')]
    .find((b) => b.textContent?.trim() === label)
  if (!button) return
  if (button.getAttribute('aria-expanded') !== 'true') button.click()
  button.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

export function OrdersBar({ state, selected }: { state: GameState; selected?: string }) {
  const nation = selected ? state.nations[selected] : undefined
  if (!selected || !nation) return null
  const own = selected === state.seat.nation
  const rel = relationBetween(state, state.seat.nation, selected)
  const feeling = own ? { tone: 'self', label: 'Your nation' } : mood(state, selected)
  const canIntel = !own && state.seat.role !== 'mediator'
  return (
    <div className="orders-bar" style={nationStyle(selected) as CSSProperties} data-mood={feeling.tone}>
      <div className="orders-who">
        {portraitOf(selected) && <img src={portraitOf(selected)} alt="" />}
        <div>
          <strong>{nation.name}</strong>
          <span>{nation.leader} · {systemLabels[nation.system] ?? nation.system}</span>
          <em>{feeling.label}{rel !== undefined && ` ${rel > 0 ? '+' : ''}${rel}`}{nation.beliefs && ` · trust ${Math.round(nation.beliefs.trust_in_player * 100)}%`}</em>
        </div>
      </div>
      {!own && (
        <div className="orders-actions" role="group" aria-label={`Orders for ${nation.name}`}>
          <button className="order order-call" onClick={openCall}>
            <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5.5 2.5l3 3-2 2.2c1 2.2 2.6 3.8 4.8 4.8l2.2-2 3 3-2 2.5C9.5 16 4 10.5 3 4.5z" /></svg>
            Call {nation.leader.split(' ').slice(-1)[0]}
          </button>
          {canIntel && <button className="order" onClick={() => openDossierTab('Intel')}>Intel</button>}
          {canIntel && <button className="order" onClick={() => openDossierTab('Wiretap')}>Wiretap</button>}
          {Diplomacy && <Diplomacy state={state} target={selected} />}
        </div>
      )}
    </div>
  )
}
