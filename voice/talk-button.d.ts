// Types for voice/talk-button.js. See voice/TALK_BUTTON.md.

export type TalkState = 'idle' | 'recording' | 'thinking' | 'speaking' | 'disabled'

export interface TalkButtonOptions {
  /** Nation id of the leader on the line, or null for no call (button disabled). */
  to?: string | null
  /** Prefix for /call and /audio. Default '/api'. */
  apiBase?: string
  /** Show the typed fallback field. Default true. */
  typed?: boolean
  /** Hold the space bar to talk. Default true. */
  spaceBar?: boolean
}

export interface CallReplyDetail {
  to: string
  transcript: string
  reply_text: string
  reply_audio_url: string | null
  emotion: string
  promises: { to: string; what: string; when: string; condition: string | null }[]
  actions: { type: string; by: string; target?: string | null; params?: Record<string, unknown> }[]
}

export interface TalkButtonEvents {
  transcript: CustomEvent<{ text: string; to: string }>
  reply: CustomEvent<CallReplyDetail>
  'audio-start': CustomEvent<{ url: string; speaker: string }>
  'audio-end': CustomEvent<{ url: string; speaker: string; interrupted: boolean }>
  'talk-state': CustomEvent<{ state: TalkState }>
  error: CustomEvent<{ message: string }>
}

export interface TalkButton {
  setTo(nation: string | null): void
  playLine(url: string | null, speaker?: string): Promise<void>
  stop(): void
  readonly state: TalkState
  destroy(): void
}

export function mountTalkButton(el: HTMLElement, opts?: TalkButtonOptions): TalkButton
