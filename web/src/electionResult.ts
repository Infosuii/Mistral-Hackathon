import type { GameState } from './state'

// The closing vote on the end screen. Everything here is derived from the final state the
// backend already sends (nation stats and the ending score), so the engine is untouched.

export interface Pillar { label: string; value: number }
export interface Election {
  body: string          // who votes: "General election", "Council of Generals", ...
  counting: string      // the line shown while the count runs
  unit: string          // what is reporting: "Districts", "Barracks", ...
  you: string           // the player's side of the count
  rival: string         // the other side
  share: number         // the player's final share, 0-100
  won: boolean
  verdict: string       // the stamped result: "RE-ELECTED", "DEPOSED", ...
  line: string          // one sentence under the stamp
  noVote: boolean       // a coup: no count, the result is shown at once
  score: number         // overall leadership score, 0-100
  title: string         // a name for the leadership style the score earned
  pillars: Pillar[]
  honours: string[]
}

const clamp = (value: number, low = 0, high = 100) => Math.min(high, Math.max(low, value))

const bodies: Record<string, { body: string; counting: string; unit: string; rival: string; won: string; lost: string }> = {
  democracy: { body: 'General election', counting: 'Polls have closed. Counting the votes…', unit: 'Districts',
    rival: 'Opposition', won: 'RE-ELECTED', lost: 'VOTED OUT' },
  junta: { body: 'Council of Generals', counting: 'The generals are casting their ballots…', unit: 'Garrisons',
    rival: 'Colonels', won: 'COMMAND RETAINED', lost: 'DEPOSED' },
  one_party: { body: 'Party Congress', counting: 'Delegates are voting behind closed doors…', unit: 'Delegations',
    rival: 'Rival faction', won: 'RECONFIRMED', lost: 'REPLACED' },
  monarchy: { body: 'Royal Court', counting: 'The court is weighing your reign…', unit: 'Great houses',
    rival: 'Pretenders', won: 'THE CROWN ENDURES', lost: 'ABDICATION' },
  technocracy: { body: 'Board of Governors', counting: 'The board is reviewing your mandate…', unit: 'Ministries',
    rival: 'Reform bloc', won: 'MANDATE RENEWED', lost: 'MANDATE ENDED' },
}

export function election(state: GameState): Election | null {
  const ending = state.ending
  if (!ending) return null
  const score = ending.score
  const months = Math.max(1, score.months_in_power)
  const peace = clamp((score.peace_months / months) * 100)
  const promises = score.promises_kept + score.promises_broken
  const trust = promises ? (score.promises_kept / promises) * 100 : 70

  if (state.seat.role === 'mediator' || !state.seat.nation) {
    const crises = score.peaceful_crises ?? 0
    const avgTrust = (score.average_trust ?? 0.5) * 100
    const share = clamp(30 + crises * 18 + avgTrust * 0.35, 12, 92)
    const won = share >= 50
    const pillars = [
      { label: 'Peace', value: clamp(40 + crises * 30) },
      { label: 'Trust', value: clamp(avgTrust) },
      { label: 'Even-handedness', value: clamp(trust) },
    ]
    const total = Math.round(pillars.reduce((sum, p) => sum + p.value, 0) / pillars.length)
    return {
      body: 'Peace Committee', counting: 'The committee is voting on your mediation…', unit: 'Committee seats',
      you: 'For the award', rival: 'Against', share, won, noVote: false,
      verdict: won ? 'PEACE PRIZE AWARDED' : 'NOMINATED',
      line: won ? 'The committee honours the mediator who kept the region talking.'
        : 'Not this year, but the nomination alone puts you in rare company.',
      score: total, ...rank(total), pillars,
      honours: [
        crises > 0 && `${crises} crisis${crises === 1 ? '' : 'es'} resolved without war`,
        avgTrust >= 60 && 'Trusted by the leaders on both sides',
      ].filter(Boolean) as string[],
    }
  }

  const nation = state.nations[state.seat.nation]
  const system = bodies[nation?.system ?? 'democracy'] ?? bodies.democracy
  const approval = nation?.stats.approval ?? 50
  const stability = nation?.stats.stability ?? 50
  const economy = clamp(50 + score.gdp_change * 2.5)
  const steadiness = clamp(stability + score.stability_change)
  // the share of the vote: mostly approval, lifted by peace, prosperity and kept word
  let share = clamp(18 + approval * 0.45 + stability * 0.15 + peace * 0.1 + score.gdp_change * 0.3
    + score.promises_kept * 2 - score.promises_broken * 3, 14, 86)
  if (ending.reason === 'voted_out') share = Math.min(share, 46)
  const noVote = ending.reason === 'coup'
  const won = !noVote && share >= 50
  const pillars = [
    { label: 'Popularity', value: clamp(noVote ? approval * 0.6 : share * 1.25 - 10) },
    { label: 'Economy', value: economy },
    { label: 'Stability', value: steadiness },
    { label: 'Peace', value: peace },
    { label: 'Trust', value: clamp(trust) },
  ]
  const total = Math.round(0.25 * pillars[0].value + 0.2 * economy + 0.15 * steadiness + 0.2 * peace + 0.2 * clamp(trust))
  const leader = nation?.leader ?? 'You'
  const honours = [
    score.peace_months >= months && 'Not a single month at war',
    score.gdp_change >= 5 && `Economy up ${Math.round(score.gdp_change)} points`,
    score.promises_kept > 0 && score.promises_broken === 0 && 'Kept every promise made on the phone',
    score.stability_change >= 5 && 'Left the country steadier than you found it',
    months >= 12 && 'Served the full year in office',
  ].filter(Boolean) as string[]
  return {
    body: system.body, counting: system.counting, unit: system.unit,
    you: leader, rival: system.rival, share, won, noVote,
    verdict: noVote ? 'OVERTHROWN' : won ? system.won : system.lost,
    line: noVote ? 'The tanks moved first. History will judge the year you had.'
      : won ? `${nation?.name ?? 'The nation'} gives ${leader} another term.`
        : 'Power changes hands peacefully: the system you protected still stands.',
    score: total, ...rank(total), pillars, honours,
  }
}

function rank(score: number): { title: string } {
  if (score >= 85) return { title: 'Legendary statesman' }
  if (score >= 72) return { title: 'Statesman' }
  if (score >= 60) return { title: 'Steady hand' }
  if (score >= 45) return { title: 'Survivor' }
  return { title: 'Hard lessons learned' }
}
