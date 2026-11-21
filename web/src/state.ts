import fixture from '../../contracts/examples/state.json'
import oneBerth from '../../contracts/examples/crisis_file.one_berth.json'

export interface Stats {
  gdp: number
  oil: number
  food: number
  chips: number
  army: number
  stability: number
  approval: number
  territory: number
}

export interface Nation {
  name: string
  system: string
  leader: string
  voice_id: string
  stats: Stats
  beliefs: { trust_in_player: number; resolve_of_player: number } | null
  public_statement: string
  status: string[]
}

export const defaultCrisis = { id: oneBerth.id, title: oneBerth.title }

interface CrisisOption {
  id: string
  title: string
}

export interface CrisisState {
  id: string
  tick: number
  ticks_total: number
  deadlines: Record<string, number>
  promises: { id: string; by: string; to: string; what: string; when: string; condition: string | null; kept: boolean | null }[]
  public_commitments: { nation: string; action: string; tick: number }[]
  decisions: Record<string, { action: string; tick: number }>
}

export interface Futures {
  before: { war_p: number }
  after: { war_p: number }
  caption: string
}

interface LastCall {
  call_id: string
  to: string
  pending: boolean
  promises: { to: string; what: string; when: string; condition?: string | null }[]
}

interface SessionScore {
  months_in_power: number
  peace_months: number
  gdp_change: number
  stability_change: number
  promises_kept: number
  promises_broken: number
  peaceful_crises?: number | null
  average_trust?: number | null
}

export interface GameState {
  turn: number
  phase: string
  seed: number
  seat: { role: string; nation: string | null }
  available_roles?: string[] | null
  available_crises?: CrisisOption[] | null
  nations: Record<string, Nation>
  relations: Record<string, number>
  links: { type: string; a: string; b: string }[]
  provinces: Record<string, string>
  news: { turn: number; text: string }[]
  events: { turn: number; type: string; nation?: string | null; province?: string | null }[]
  incoming_call: { from: string; emotion: string; opening_line: string; audio_url?: string | null } | null
  crisis: CrisisState | null
  last_futures: Futures | null
  last_call?: LastCall | null
  ending?: { reason: string; score: SessionScore; verdict: string | null } | null
}

export const exampleState: GameState = fixture

export const statLabels = {
  gdp: 'Economy',
  oil: 'Oil',
  food: 'Food',
  chips: 'Chips',
  army: 'Army',
  stability: 'Stability',
  approval: 'Approval',
  territory: 'Territory',
} satisfies Record<keyof Stats, string>

export const systemLabels: Record<string, string> = {
  democracy: 'Parliamentary democracy',
  junta: 'Military junta',
  monarchy: 'Constitutional monarchy',
  technocracy: 'Technocracy',
  one_party: 'One-party state',
}

export function relationBetween(state: GameState, a: string | null, b: string | undefined) {
  if (a && b && a !== b) return state.relations[[a, b].sort().join('|')]
}
