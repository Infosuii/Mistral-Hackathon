// The War Room (GAMBIT_WAR=1 on the backend): declare war, pick a province to attack,
// watch troops march between provinces, recruit, make peace or pay/demand tribute, sign
// pacts, and read the battle log and war scores. The engine decides everything
// (GET/POST /war...); the page only shows it and forwards clicks.
import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { api, post } from '../api'
import map from '../atlas.json'
import { useMarkerScale } from './scale'
import { relationBetween, type GameState } from '../state'
import { nationStyle } from '../theme'
import './war.css'

export interface WarView {
  enabled: boolean
  player: string | null
  garrisons: Record<string, { owner: string; troops: number }>
  capitals: Record<string, string>
  armies: { id: number; owner: string; from: string; to: string; troops: number; progress: number; eta_s: number; target: string }[]
  wars: { a: string; b: string; started_turn: number; battles: number; score: Record<string, number>; taken: Record<string, number>; lost: Record<string, number> }[]
  troops: Record<string, number>
  recruiting: { nation: string; troops: number; ready_in_s: number }[]
  pacts: Record<string, number>
  log: { t: number; turn: number; kind: string; text: string; province?: string; winner?: string; attacker?: string; defender?: string }[]
  message?: string
  reply?: string
  accepted?: boolean
}

const centers = new Map(map.provinces.map(({ id, center }) => [id, center as number[]]))
const adjacency = new Map<string, Set<string>>()
for (const { between: [a, b] } of map.borders) {
  adjacency.set(a, (adjacency.get(a) ?? new Set()).add(b))
  adjacency.set(b, (adjacency.get(b) ?? new Set()).add(a))
}

export const fmtTroops = (n: number) => (n >= 10000 ? `${Math.round(n / 1000)}k` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${Math.round(n)}`)
const key = (a: string, b: string) => [a, b].sort().join('|')

export function useWar(state: GameState) {
  const [war, setWar] = useState<WarView | null>(null)
  const [fetchedAt, setFetchedAt] = useState(0)
  const [attackMode, setAttackModeRaw] = useState(false)
  // Entering attack mode zooms the map out if none of the striped targets are on screen
  // (the atlas opens zoomed into your capital, so the enemy is usually off view).
  const setAttackMode = useCallback((on: boolean) => {
    setAttackModeRaw(on)
    if (!on) return
    window.setTimeout(() => {
      const visible = [...document.querySelectorAll('path[data-war-target="true"]')].some((p) => {
        const r = p.getBoundingClientRect()
        return r.right > 0 && r.bottom > 0 && r.left < window.innerWidth && r.top < window.innerHeight
      })
      if (!visible) [...document.querySelectorAll('button')].find((b) => /fit map/i.test(b.textContent ?? ''))?.click()
    }, 120)
  }, [])
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState(false)
  const off = useRef(false)

  const accept = useCallback((v: WarView) => {
    setWar(v)
    setFetchedAt(performance.now())
  }, [])

  useEffect(() => {
    let stop = false
    async function poll() {
      try {
        accept(await api<WarView>('/war', { cache: 'no-store' }))
        off.current = false
      } catch {
        off.current = true
        setWar(null)
      }
    }
    void poll()
    const timer = window.setInterval(() => { if (!stop && (!off.current || Math.random() < 0.08)) void poll() }, 600)
    return () => { stop = true; window.clearInterval(timer) }
  }, [accept, state.seed, state.seat.nation])

  const act = useCallback(async (path: string, body: unknown, ok?: (v: WarView) => string | undefined) => {
    setBusy(true)
    try {
      const v = await post<WarView>(path, body)
      accept(v)
      setNotice(ok?.(v) ?? v.reply ?? v.message ?? '')
    } catch (e) {
      const text = String((e as Error).message)
      setNotice(text.includes('422') ? 'Not possible right now: check the border, troops or economy.' : text)
    } finally {
      setBusy(false)
    }
  }, [accept])

  // POST errors carry the reason in the body; fetch it for a readable notice.
  const explain = useCallback(async (path: string, body: unknown) => {
    const r = await fetch(`/api${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
    const data = await r.json().catch(() => ({}))
    if (r.ok) {
      accept(data)
      setNotice(data.reply ?? data.message ?? '')
    } else {
      setNotice(typeof data.detail === 'string' ? data.detail : `HTTP ${r.status}`)
    }
    return r.ok
  }, [accept])

  return {
    war, fetchedAt, attackMode, setAttackMode, notice, setNotice, busy,
    declare: (target: string) => explain('/war/declare', { target }),
    attack: (province: string) => explain('/war/attack', { province, share: 0.7, advance: true }),
    recruit: (troops: number) => explain('/war/recruit', { troops }),
    reinforce: (target: string) => explain('/war/reinforce', { target }),
    peace: (target: string, kind: string, amount = 0) => explain('/war/peace', { target, kind, amount }),
    act,
  }
}

export type WarControls = ReturnType<typeof useWar>

/** Provinces the player can attack right now: enemy provinces bordering one of theirs. */
export function attackable(state: GameState, war: WarView | null): Set<string> {
  const me = war?.player
  if (!war || !me) return new Set()
  const enemies = new Set(war.wars.flatMap((w) => (w.a === me ? [w.b] : w.b === me ? [w.a] : [])))
  const out = new Set<string>()
  for (const [p, owner] of Object.entries(state.provinces)) {
    if (!enemies.has(owner)) continue
    if ([...(adjacency.get(p) ?? [])].some((q) => state.provinces[q] === me)) out.add(p)
  }
  return out
}

function useFrame(active: boolean) {
  const [, setTick] = useState(0)
  useEffect(() => {
    if (!active) return
    let raf = 0
    const loop = () => { setTick((t) => t + 1); raf = requestAnimationFrame(loop) }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [active])
}

/** Inside the map camera: troop badges, marching armies, battle bursts, attack targets. */
export function WarMapLayer({ state, controls, showAll = false }: { state: GameState; controls: WarControls; showAll?: boolean }) {
  const { war, fetchedAt, attackMode } = controls
  const m = useMarkerScale()
  useFrame(Boolean(war?.armies.length))
  if (!war) return null
  const targets = attackMode ? attackable(state, war) : new Set<string>()
  // Troop badges for nations at war (and everyone in Military map mode), not all 40 provinces.
  const fighting = new Set(war.wars.flatMap((w) => [w.a, w.b]))
  const now = performance.now()
  const recent = war.log.filter((e) => e.kind === 'battle' && e.province).slice(-4)
  const lastT = war.log.length ? war.log[war.log.length - 1].t : 0
  return (
    <g className="war-layer">
      <defs>
        <pattern id="war-room-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform={`rotate(45) scale(${m * 1.6})`}>
          <rect width="4" height="10" fill="var(--war)" opacity=".4" />
        </pattern>
      </defs>
      <g className="war-targets">
        {map.provinces.filter((p) => targets.has(p.id)).map((p) => (
          <path key={p.id} d={p.path} className="war-target" style={{ strokeWidth: 2.5 * m }} />
        ))}
      </g>
      <g className="garrisons map-decoration">
        {Object.entries(war.garrisons).map(([p, g]) => {
          const c = centers.get(p)
          if (!c || g.troops < 1 || !(showAll || fighting.has(g.owner))) return null
          const capital = war.capitals[g.owner] === p
          return (
            <g key={p} transform={`translate(${c[0]} ${c[1] - 30 * m}) scale(${m * 1.6})`} style={nationStyle(g.owner) as CSSProperties}
              className="garrison" data-capital={capital}>
              <rect x="-15" y="-7" width="30" height="13" rx="2" />
              <text y="3.5">{fmtTroops(g.troops)}</text>
            </g>
          )
        })}
      </g>
      <g className="armies map-decoration">
        {war.armies.map((a) => {
          const from = centers.get(a.from)
          const to = centers.get(a.to)
          if (!from || !to) return null
          const total = a.eta_s / Math.max(0.001, 1 - a.progress)
          const extra = total > 0 ? (now - fetchedAt) / 1000 / total : 0
          const k = Math.min(1, a.progress + extra)
          const x = from[0] + (to[0] - from[0]) * k
          const y = from[1] + (to[1] - from[1]) * k
          const angle = Math.atan2(to[1] - from[1], to[0] - from[0]) * 180 / Math.PI
          return (
            <g key={a.id} style={nationStyle(a.owner) as CSSProperties}>
              <path className="march-path" d={`M${from[0]},${from[1]} L${to[0]},${to[1]}`} style={{ strokeWidth: 2.4 * m, strokeDasharray: `${6 * m} ${5 * m}` }} />
              <g className="army-token" transform={`translate(${x} ${y}) scale(${m * 1.8})`}>
                <g transform={`rotate(${angle})`}><path className="army-arrow" d="M12,0 L-6,-8 L-2,0 L-6,8 Z" /></g>
                <rect x="-14" y="10" width="28" height="12" rx="6" className="army-plate" />
                <text y="19.5" className="army-count">{fmtTroops(a.troops)}</text>
              </g>
            </g>
          )
        })}
      </g>
      <g className="battles map-decoration">
        {recent.map((e) => {
          const c = centers.get(e.province!)
          if (!c || lastT - e.t > 4) return null
          return (
            <g key={`${e.t}-${e.province}`} transform={`translate(${c[0]} ${c[1]}) scale(${m * 2})`} style={nationStyle(e.winner ?? '') as CSSProperties}>
              <circle r="10" className="battle-burst" />
              <path className="battle-x" d="M-7,-7 L7,7 M7,-7 L-7,7" />
            </g>
          )
        })}
      </g>
    </g>
  )
}

/** The War Room panel over the map. */
export function WarRoomPanel({ state, selected, controls }: { state: GameState; selected?: string; controls: WarControls }) {
  const { war, attackMode, setAttackMode, notice, setNotice, busy } = controls
  const [open, setOpen] = useState(true)
  const [showLog, setShowLog] = useState(false)
  if (!war || !war.player) return null
  const me = war.player
  const target = selected && selected !== me && state.nations[selected] ? selected : null
  const myWars = war.wars.filter((w) => w.a === me || w.b === me)
  const atWarWith = (n: string) => myWars.some((w) => w.a === n || w.b === n)
  const pact = target ? war.pacts[key(me, target)] : undefined
  const rel = target ? relationBetween(state, me, target) : undefined
  const targets = attackable(state, war)
  const battles = war.log.filter((e) => ['battle', 'declare', 'peace', 'pact'].includes(e.kind)).slice(-(showLog ? 30 : 5)).reverse()
  const marching = war.armies.filter((a) => a.owner === me).reduce((s, a) => s + a.troops, 0)

  return (
    <section className="war-room" data-open={open} data-attack={attackMode}>
      <header>
        <button className="war-title" onClick={() => setOpen(!open)} aria-expanded={open}>
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 17L13 7M7 3l10 10M13 3l4 4-2 2M3 13l4 4" /></svg>
          War Room {myWars.length > 0 && <span className="war-count">{myWars.length} at war</span>}
        </button>
      </header>
      {open && (
        <>
          <div className="war-forces">
            <span>Your forces <b>{fmtTroops(war.troops[me] ?? 0)}</b></span>
            {marching > 0 && <span>marching <b>{fmtTroops(marching)}</b></span>}
            {war.recruiting.filter((r) => r.nation === me).map((r, i) => <span key={i}>training <b>{fmtTroops(r.troops)}</b> · {Math.ceil(r.ready_in_s)}s</span>)}
            <button className="war-btn" disabled={busy} onClick={() => void controls.recruit(1000)} title="Costs 10 economy; ready in 5 s at your capital">
              Recruit 1k <small>−10 econ</small>
            </button>
          </div>

          {target ? (
            <div className="war-target-box" style={nationStyle(target) as CSSProperties}>
              <div className="war-target-name">
                <strong>{state.nations[target].name}</strong>
                <span>{fmtTroops(war.troops[target] ?? 0)} troops{rel !== undefined && ` · relations ${rel > 0 ? '+' : ''}${rel}`}{pact ? ` · pact ${Math.ceil(pact)}s` : ''}</span>
              </div>
              {!atWarWith(target) ? (
                <div className="war-actions">
                  <button className="war-btn war-declare" disabled={busy} onClick={() => {
                    if (pact && !window.confirm('You have a non-aggression pact. Break it? Trust will fall.')) return
                    void controls.declare(target).then((ok) => ok && setAttackMode(true))
                  }}>Declare war</button>
                  <button className="war-btn" disabled={busy || Boolean(pact)} onClick={() => void controls.peace(target, 'pact')}>Offer non-aggression pact</button>
                </div>
              ) : (
                <div className="war-actions">
                  <button className="war-btn war-attack" data-on={attackMode} onClick={() => { setAttackMode(!attackMode); setNotice(attackMode ? '' : targets.size ? 'Click a red-striped province to attack it.' : 'No enemy province borders yours.') }}>
                    {attackMode ? 'Cancel attack' : 'Attack a province'}
                  </button>
                  <button className="war-btn" disabled={busy} onClick={() => void controls.reinforce(target)} title="March spare troops from your interior to this front">Reinforce front</button>
                  <button className="war-btn" disabled={busy} onClick={() => void controls.peace(target, 'white')}>Offer peace</button>
                  <button className="war-btn" disabled={busy} onClick={() => void controls.peace(target, 'pay', 15)}>Pay tribute <small>15</small></button>
                  <button className="war-btn" disabled={busy} onClick={() => void controls.peace(target, 'demand', 15)}>Demand tribute</button>
                </div>
              )}
            </div>
          ) : (
            <p className="war-hint">Select a nation on the map to declare war, attack or make peace.</p>
          )}

          {notice && <p className="war-notice" role="status">{notice}</p>}

          {myWars.length > 0 && (
            <ul className="war-scores">
              {myWars.map((w) => {
                const enemy = w.a === me ? w.b : w.a
                const mine = w.score[me] ?? 0
                const theirs = w.score[enemy] ?? 0
                const lead = mine - theirs
                return (
                  <li key={key(w.a, w.b)} style={nationStyle(enemy) as CSSProperties}>
                    <span className="ws-name">vs {state.nations[enemy]?.name}</span>
                    <span className="ws-bar"><i style={{ width: `${Math.max(5, Math.min(95, 50 + lead * 2))}%` }} /></span>
                    <span className="ws-detail" data-sign={Math.sign(lead)}>
                      {lead > 0 ? 'Winning' : lead < 0 ? 'Losing' : 'Even'} · took {w.taken[me] ?? 0}, lost {w.taken[enemy] ?? 0} · {w.battles} battles
                    </span>
                  </li>
                )
              })}
            </ul>
          )}

          <div className="war-log">
            <div className="war-log-head">
              <span>Battle history</span>
              <button onClick={() => setShowLog(!showLog)}>{showLog ? 'Less' : 'All'}</button>
            </div>
            {battles.length ? (
              <ol>
                {battles.map((e, i) => (
                  <li key={`${e.t}-${i}`} data-kind={e.kind} style={nationStyle(e.winner ?? e.attacker ?? '') as CSSProperties}>
                    <span className="wl-turn">M{e.turn}</span>{e.text}
                  </li>
                ))}
              </ol>
            ) : <p className="war-hint">No battles yet.</p>}
          </div>
        </>
      )}
    </section>
  )
}
