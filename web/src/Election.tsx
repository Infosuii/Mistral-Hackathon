import { useEffect, useMemo, useRef, useState } from 'react'
import { election, type Election as Result } from './electionResult'
import type { GameState } from './state'
import './election.css'

const COUNT_MS = 4200   // the drum roll and the live count
const SCORE_MS = 1400   // the leadership score counting up after the stamp
const confettiColors = ['var(--accent)', 'var(--gain)', 'var(--alliance)', 'var(--paper)', 'var(--signal)']

type Stage = 'counting' | 'reveal' | 'done'

const reducedMotion = () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
const ease = (t: number) => 1 - Math.pow(1 - t, 3)

function soundPref(): boolean {
  try { return localStorage.getItem('gambit-election-sound') !== 'off' } catch { return true }
}

// A drum roll that builds for the length of the count, then a crash and a chord. Synthesised with
// Web Audio so there is no file to ship; silent if the browser blocks audio.
function playFinale(won: boolean, rollMs: number): () => void {
  let ctx: AudioContext | null = null
  try {
    const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
    if (!Ctor) return () => {}
    ctx = new Ctor()
    void ctx.resume().catch(() => {})
    const c = ctx
    const noise = c.createBuffer(1, c.sampleRate, c.sampleRate)
    const data = noise.getChannelData(0)
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
    const master = c.createGain()
    master.gain.value = 0.5
    master.connect(c.destination)
    const hit = (at: number, level: number, decay: number, cutoff: number) => {
      const src = c.createBufferSource()
      src.buffer = noise
      const filter = c.createBiquadFilter()
      filter.type = 'highpass'
      filter.frequency.value = cutoff
      const gain = c.createGain()
      gain.gain.setValueAtTime(level, at)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + decay)
      src.connect(filter).connect(gain).connect(master)
      src.start(at, Math.random() * 0.5, decay + 0.05)
    }
    const start = c.currentTime + 0.05
    const end = start + rollMs / 1000
    for (let t = start; t < end;) {
      const p = (t - start) / (end - start)
      hit(t, 0.08 + 0.32 * p * p, 0.07, 900)
      t += 0.085 - 0.05 * p
    }
    hit(end, 0.9, 1.8, 4000)  // crash
    const notes = won ? [261.63, 329.63, 392.0, 523.25] : [220.0, 261.63, 329.63]
    for (const [i, freq] of notes.entries()) {
      const osc = c.createOscillator()
      osc.type = won ? 'sawtooth' : 'sine'
      osc.frequency.value = freq
      const filter = c.createBiquadFilter()
      filter.type = 'lowpass'
      filter.frequency.value = won ? 1800 : 900
      const gain = c.createGain()
      const at = end + (won ? i * 0.06 : 0)
      gain.gain.setValueAtTime(0.0001, at)
      gain.gain.exponentialRampToValueAtTime(won ? 0.12 : 0.08, at + 0.04)
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 1.6)
      osc.connect(filter).connect(gain).connect(master)
      osc.start(at)
      osc.stop(at + 1.7)
    }
  } catch {
    // no audio: the finale still plays on screen
  }
  return () => { void ctx?.close().catch(() => {}) }
}

export function ElectionFinale({ state }: { state: GameState }) {
  // The state is re-fetched on every poll; key the finale on what it is computed from, so a new
  // poll (or the historian's verdict arriving) does not restart the count.
  const nation = state.seat.nation ? state.nations[state.seat.nation] : null
  const key = JSON.stringify([state.ending?.reason, state.ending?.score, state.seat, nation?.system, nation?.stats])
  const result = useMemo(() => election(state), [key])  // eslint-disable-line react-hooks/exhaustive-deps
  const instant = reducedMotion()
  const [run, setRun] = useState(0)
  const [stage, setStage] = useState<Stage>(instant ? 'done' : 'counting')
  const [progress, setProgress] = useState(instant ? 1 : 0)
  const [scoreShown, setScoreShown] = useState(instant ? (result?.score ?? 0) : 0)
  const [sound, setSound] = useState(soundPref)
  const stop = useRef<() => void>(() => {})

  useEffect(() => {
    if (!result) return
    if (instant) { setStage('done'); setProgress(1); setScoreShown(result.score); return }
    const roll = result.noVote ? 600 : COUNT_MS
    setStage(result.noVote ? 'reveal' : 'counting')
    setProgress(result.noVote ? 1 : 0)
    setScoreShown(0)
    stop.current = sound ? playFinale(result.won, roll) : () => {}
    const began = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const t = now - began
      if (t < roll) {
        setProgress(t / roll)
      } else {
        setProgress(1)
        setStage((s) => (s === 'counting' ? 'reveal' : s))
        const k = Math.min(1, (t - roll - 500) / SCORE_MS)
        setScoreShown(Math.round(result.score * ease(Math.max(0, k))))
        if (k >= 1) { setStage('done'); return }
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(frame); stop.current() }
  }, [key, run])  // eslint-disable-line react-hooks/exhaustive-deps

  if (!result) return null

  function skip() {
    stop.current()
    setProgress(1)
    setScoreShown(result!.score)
    setStage('done')
  }

  function toggleSound() {
    const next = !sound
    setSound(next)
    if (!next) stop.current()
    try { localStorage.setItem('gambit-election-sound', next ? 'on' : 'off') } catch { /* private mode */ }
  }

  const counted = stage !== 'counting'
  const yourShare = liveShare(result, progress)
  return (
    <section className="election" data-stage={stage} data-won={result.won} aria-labelledby="election-heading">
      <header className="election-head">
        <p className="election-body">{result.body}</p>
        <h3 id="election-heading">{counted ? 'The result is in' : result.counting}</h3>
        <div className="election-tools">
          <button type="button" onClick={toggleSound} aria-pressed={sound}>{sound ? 'Sound on' : 'Sound off'}</button>
          {stage === 'done'
            ? <button type="button" onClick={() => setRun((r) => r + 1)}>Replay the count</button>
            : <button type="button" onClick={skip}>Skip</button>}
        </div>
      </header>

      {!result.noVote && (
        <div className="election-count">
          <div className="election-bar">
            <span className="election-you" style={{ width: `${yourShare}%` }}>
              <b>{result.you}</b> {yourShare.toFixed(1)}%
            </span>
            <span className="election-rival" style={{ width: `${100 - yourShare}%` }}>
              {(100 - yourShare).toFixed(1)}% <b>{result.rival}</b>
            </span>
          </div>
          <p className="election-reporting">
            {result.unit} reporting <b>{Math.round(progress * 100)}%</b>
            <span className="election-majority" aria-hidden="true">50% to win</span>
          </p>
        </div>
      )}

      <div className="election-stage" aria-live="polite">
        {counted && (
          <>
            <p className="election-stamp">{result.verdict}</p>
            <p className="election-line">{result.line}</p>
            {result.won && stage === 'reveal' && (
              <div className="confetti" aria-hidden="true">
                {Array.from({ length: 56 }, (_, i) => (
                  <i key={`${run}-${i}`} style={{
                    left: `${(i * 37) % 100}%`,
                    background: confettiColors[i % confettiColors.length],
                    animationDelay: `${(i % 14) * 0.07}s`,
                    animationDuration: `${2.2 + (i % 5) * 0.35}s`,
                    transform: `rotate(${i * 47}deg)`,
                  }} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      {counted && (
        <div className="leadership">
          <div className="leadership-score">
            <span>Leadership score</span>
            <b>{scoreShown}</b>
            <small>/ 100</small>
            <em>{result.title}</em>
          </div>
          <ul className="leadership-pillars">
            {result.pillars.map(({ label, value }) => (
              <li key={label}>
                <span>{label}</span>
                <i style={{ width: `${stage === 'done' ? Math.round(value) : 0}%` }} />
                <b>{Math.round(value)}</b>
              </li>
            ))}
          </ul>
          {result.honours.length > 0 && (
            <ul className="leadership-honours" aria-label="Honours">
              {result.honours.map((honour) => <li key={honour}>{honour}</li>)}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}

// The live count wobbles and briefly trails before settling on the real share.
function liveShare(result: Result, progress: number) {
  if (progress >= 1) return result.share
  const p = ease(progress)
  const wobble = Math.sin(progress * Math.PI * 5) * (1 - progress) * 7
  return Math.min(96, Math.max(4, 50 + (result.share - 50) * p + wobble))
}
