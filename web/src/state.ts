import fallback from './state.example.json'

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
  beliefs: { trust_in_player: number; resolve_of_player: number }
  public_statement: string
  status: string[]
}

export interface GameState {
  turn: number
  phase: string
  seed: number
  seat: { role: string; nation: string | null }
  nations: Record<string, Nation>
  relations: Record<string, number>
  links: { type: string; a: string; b: string }[]
  provinces: Record<string, string>
  news: { turn: number; text: string }[]
  events: { turn: number; type: string; nation: string }[]
  incoming_call: { from: string; emotion: string; opening_line?: string } | null
  crisis: { id: string; tick: number; ticks_total: number } | null
  last_futures: unknown
}

const fixtures = import.meta.glob<GameState>('../../contracts/examples/state.json', {
  eager: true,
  import: 'default',
})

export const exampleState: GameState = fixtures['../../contracts/examples/state.json'] ?? fallback

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
