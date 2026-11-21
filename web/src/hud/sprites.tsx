// Small top-down vehicle sprites in world units, facing +x. Nation colours come from
// --nation-fill / --nation-accent on an ancestor.

export function Car({ tone = 0 }: { tone?: number }) {
  const body = ['#d6d2c4', '#b8453a', '#3f6f8f', '#e0b84a', '#5c6b62', '#efefe8'][tone % 6]
  return <g>
    <path fill="#0e1a1c" opacity=".35" d="M-2 -1.1h5.4v3.2H-2Z" />
    <path fill={body} d="M-2.6-1.4h5.2v2.8h-5.2Z" />
    <path fill="#22343a" d="M-.4-1.1h1.6v2.2h-1.6Z" />
  </g>
}

export function Truck({ tone = 0 }: { tone?: number }) {
  return <g>
    <path fill="#0e1a1c" opacity=".3" d="M-4.6-1.4h11v4h-11Z" />
    <path fill="#1f2a2e" d="M-5.5-2h11v4h-11Z" />
    <path fill={['#d5b07c', '#b9cbd0', '#c9876b', '#e0dccb', '#8fa86a'][tone % 5]} d="M-5-1.7h7.4v3.4H-5Z" />
    <path fill="#40606b" d="M3-1.6h2.4v3.2H3Z" />
  </g>
}

export function ArmyTruck() {
  return <g>
    <path fill="#1d2620" d="M-5.5-2.1h11v4.2h-11Z" />
    <path fill="color-mix(in srgb, var(--nation-fill, #4d5b3f), #5b5f3c 55%)" d="M-5-1.8h7.2v3.6H-5Z" />
    <path stroke="#20281f" strokeWidth=".4" d="M-3.6-1.8v3.6M-1.8-1.8v3.6M0-1.8v3.6" />
    <path fill="#3f4a35" d="M2.8-1.6h2.4v3.2H2.8Z" />
  </g>
}

export function Jeep() {
  return <g>
    <path fill="#1d2620" d="M-3-1.6h6v3.2h-6Z" />
    <path fill="color-mix(in srgb, var(--nation-fill, #4d5b3f), #6a6c46 50%)" d="M-2.6-1.3h5.2v2.6h-5.2Z" />
    <path fill="#2a332a" d="M-.4-1.1h1.4v2.2h-1.4Z" />
  </g>
}

export function Tank() {
  return <g>
    <path fill="#0d1612" opacity=".35" d="M-5 -2.4h11v6h-11Z" />
    <path fill="#1f2b24" d="M-5.5-3.2h11v6.4h-11Z" />
    <path fill="color-mix(in srgb, var(--nation-fill, #466c59), #4f5a3a 40%)" d="M-5-2.4h10v4.8h-10Z" />
    <path fill="color-mix(in srgb, var(--nation-accent, #b7c891), #55603f 45%)" d="M-2.2-1.7h4.4v3.4h-4.4Z" />
    <path stroke="#1c2620" strokeWidth="1.1" d="M1.8 0H8.4" />
    <path stroke="#9aa88a" strokeWidth=".45" d="M-5.4-3h10.8M-5.4 3h10.8" />
  </g>
}

export function Locomotive({ passenger = false }: { passenger?: boolean }) {
  return <g>
    <path fill="#0e1a1c" opacity=".3" d="M-6.5-1.3h14v4h-14Z" />
    <path fill="#1c2a2d" d="M-7-2.2h14v4.4h-14Z" />
    <path fill={passenger ? '#c64d3f' : '#e0a83a'} d="M-6.5-1.8h12v3.6h-12Z" />
    <path fill="#25373b" d="M3.6-1.4h2.4v2.8H3.6Z" />
    <path fill="#f3e9c4" d="M6.2-.6h.8v1.2h-.8Z" />
  </g>
}

export function Wagon({ kind = 0 }: { kind?: number }) {
  const fill = ['#8a5a3c', '#5e6d74', '#b9b2a0', '#d9dcd4', '#4d6e8a'][kind % 5]
  return <g>
    <path fill="#1c2a2d" d="M-6.2-2h12.4v4h-12.4Z" />
    <path fill={fill} d="M-5.8-1.7h11.6v3.4h-11.6Z" />
    {kind === 3 && <path stroke="#3e5964" strokeWidth=".7" strokeDasharray="1.2 1" d="M-5-.9h10M-5 .9h10" />}
  </g>
}

export function Airliner() {
  return <g className="airliner-sprite">
    <path fill="#13252b" opacity=".3" transform="translate(9 11)" d="M-13-1.2h20l6 1.2-6 1.2h-20ZM-2-1-8-12h3l9 11ZM-2 1-8 12h3l9-11ZM-12-1-15-5h2l3 4ZM-12 1-15 5h2l3-4Z" />
    <path fill="#eef1ec" d="M-13-1.2h20l6 1.2-6 1.2h-20Z" />
    <path fill="#c9d2d0" d="M-2-1-8-12h3l9 11ZM-2 1-8 12h3l9-11ZM-12-1-15-5h2l3 4ZM-12 1-15 5h2l3-4Z" />
    <path fill="var(--nation-accent, #c6a469)" d="M-13-1h3v2h-3ZM-6-.4h12v.8h-12Z" />
  </g>
}

export function LightPlane() {
  return <g>
    <path fill="#13252b" opacity=".3" transform="translate(5 6)" d="M-5-.6h9v1.2h-9ZM-1-6h2v12h-2Z" />
    <path fill="#f2e8cf" d="M-5-.6h9l1 .6-1 .6h-9Z" />
    <path fill="#c64d3f" d="M-1-6h2v12h-2ZM-5-2.4h1.4v4.8H-5Z" />
  </g>
}

export function Fighter() {
  return <g className="fighter-sprite">
    <path fill="#13252b" opacity=".35" transform="translate(7 8) scale(.5)" d="M-19-2h9l5-8h3l-1 8 11 1 8 2-8 2-11 1 1 8h-3l-5-8h-9l2-3Z" />
    <g transform="scale(.5)">
      <path fill="#1d373e" d="M-19-2h9l5-8h3l-1 8 11 1 8 2-8 2-11 1 1 8h-3l-5-8h-9l2-3Z" />
      <path fill="#9faea3" d="M-17-1h8l5-8h1l-1 8 11 1 5 1-5 1-11 1 1 8h-1l-5-8h-8l1-2Z" />
      <path fill="var(--nation-accent, #85a786)" d="M-8-1-4-7-5 0h8v2h-9v5l-2-4h-4V0Z" opacity=".75" />
      <path fill="#365968" d="M4 0h4l2 1-2 1H4Z" />
      <path fill="#f0a35e" d="M-21 0h3v2h-3Z" />
    </g>
  </g>
}

export function Helicopter() {
  return <g>
    <path fill="#13252b" opacity=".3" transform="translate(6 7)" d="M-4-2h7v4h-7ZM-10-.5h6v1h-6Z" />
    <path fill="color-mix(in srgb, var(--nation-fill, #4d5b3f), #4f5a3a 50%)" d="M-4-2h7v4h-7ZM-10-.5h6v1h-6Z" />
    <path className="rotor" stroke="#cfd5c6" strokeWidth=".7" d="M-7 0H7M0-7V7" />
  </g>
}

/** Civilian and naval vessels. kind: cargo, ferry, fishing, tanker, frigate, destroyer. */
export function Vessel({ kind }: { kind: 'cargo' | 'ferry' | 'fishing' | 'tanker' | 'frigate' | 'destroyer' }) {
  if (kind === 'fishing') return <g>
    <path fill="#e6eef0" opacity=".5" d="M-9-1.2h-5l-3 1.2 3 1.2h5Z" />
    <path fill="#1d2b2e" d="M-5-1.8h8l2 1.8-2 1.8h-8Z" />
    <path fill="#c25b3e" d="M-4.4-1.3h7l1.4 1.3-1.4 1.3h-7Z" />
    <path fill="#eee5c8" d="M-1-1h2.4v2h-2.4Z" />
  </g>
  if (kind === 'ferry') return <g>
    <path fill="#e6eef0" opacity=".55" d="M-16-2h-7l-4 2 4 2h7Z" />
    <path fill="#1d2b2e" d="M-14-3.6h24l4 3.6-4 3.6h-24Z" />
    <path fill="#f1f1ea" d="M-13-3h22l3 3-3 3h-22Z" />
    <path fill="#3e6f8c" d="M-11-1.6h17v3.2h-17Z" />
    <path fill="#c64d3f" d="M-3-.8h3v1.6h-3Z" />
  </g>
  if (kind === 'frigate' || kind === 'destroyer') {
    const long = kind === 'destroyer' ? 1.25 : 1
    return <g transform={`scale(${long} 1)`}>
      <path fill="#e6eef0" opacity=".55" d="M-17-2h-8l-4 2 4 2h8Z" />
      <path fill="#16262b" d="M-16-3.6h24l6 3.6-6 3.6h-24Z" />
      <path fill="color-mix(in srgb, var(--nation-fill, #546d73), #6f7c80 55%)" d="M-15-2.8h22l4.6 2.8-4.6 2.8h-22Z" />
      <path fill="#a6b0ab" d="M-6-1.8h8v3.6h-8Z" />
      <path fill="#cfd5c6" d="M-3-1h3v2h-3Z" />
      <path stroke="#28393d" strokeWidth="1.2" d="M6 0h5M-12 0h-3" />
      <path fill="var(--nation-accent, #c6a469)" d="M-14-.6h2v1.2h-2Z" />
    </g>
  }
  const hull = kind === 'tanker' ? '#7d3b33' : '#2f4d5c'
  return <g>
    <path fill="#e6eef0" opacity=".5" d="M-22-2.4h-9l-5 2.4 5 2.4h9Z" />
    <path fill="#16262b" d="M-21-4.4h34l5 4.4-5 4.4h-34Z" />
    <path fill={hull} d="M-20-3.6h32l4 3.6-4 3.6h-32Z" />
    {kind === 'tanker'
      ? <path fill="#c5c0b0" d="M-15-1.4h22v2.8h-22Z" />
      : <path fill="#c9843f" d="M-16-2.6h5v5.2h-5Zm6 0h5v5.2h-5Zm6 0h5v5.2h-5Zm6 0h5v5.2H2Z" />}
    <path fill="#e8e3d0" d="M-19.6-2.4h3v4.8h-3Z" />
  </g>
}
