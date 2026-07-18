export type ApsalLayerId = 'direction' | 'worldbuilding' | 'narrative' | 'image' | 'delivery'

export interface ApsalProtocolAttribute {
  id: string
  key?: string
  name: string
  value: string
  raw_value?: unknown
}

export interface ApsalProtocolElement {
  protocol_element_id: string
  layer_id: ApsalLayerId
  role_id: string
  label: string
  studio_type: string
  status: string
  intent: string
  raw_intent?: string
  attributes: ApsalProtocolAttribute[]
  observable: string[]
  must_preserve: string[]
  qa_expectations: string[]
  order: number
  ghost?: boolean
  participatesInPrompt?: boolean
  preview_id?: string
  preview_element_id?: string
}

export interface ApsalPreview {
  preview_id: string
  operation_id: string
  session_id: string
  layer: ApsalLayerId
  base_revision: number
  revision: number
  status: string
  stale_reason?: string | null
  origin?: 'codex' | 'studio'
  summary?: string | null
  changes?: Array<{ role_id: string; field: string; before: unknown; after: unknown }>
  invalidates_if_applied: ApsalLayerId[]
  elements: ApsalProtocolElement[]
}

export interface ApsalSessionLayer {
  status: string
  roles: string[]
  selection?: unknown[]
}

export interface ApsalProjectSnapshot {
  project_root: string
  project: {
    project_id: string
    protocol_version: string
    engine_version: string
    active_session_id?: string | null
    revision: number
  }
  compatible: boolean
  read_only: boolean
  compatibility_error?: string
  required_protocol_version?: string
  required_engine_version?: string
  revision: number
  protocol_version: string
  engine_version: string
  session: null | {
    session_id: string
    state: string
    brief: string
    shot_count: number
    authoring_mode?: 'automatic' | 'guided'
    set_strategy?: string
    language?: { code?: 'zh-CN' | 'en'; status?: string }
    layers: Partial<Record<ApsalLayerId, ApsalSessionLayer>>
    invalidations: Array<{ source: ApsalLayerId; invalidated: ApsalLayerId; at: string }>
    theme_artifact?: { prompt_package?: { path: string; sha256: string } } | null
  }
  theme?: { id: string; version: string; name?: string; digest: string }
  elements: ApsalProtocolElement[]
  previews: ApsalPreview[]
  stage_previews: Array<{
    layer: ApsalLayerId
    title: string
    summary: string
    status: string
    current: boolean
    data_uri: string
  }>
}

export interface ApsalStudioView {
  schema_version: string
  view_revision: number
  nodes: Record<string, { x: number; y: number; collapsed?: boolean }>
  viewport: { x?: number; y?: number; zoom?: number }
  selected_element_id?: string | null
  expanded_cards?: string[]
  recovered_from_invalid_view?: boolean
}

export interface ApsalProtocolStatus {
  running: boolean
  compatible: boolean
  protocol_version: string
  engine_version: string
  error?: string | null
  project_root?: string
  project_id?: string
  session_id?: string
  revision?: number
}

export interface ApsalLinkStatus {
  connected: boolean
  enabled: boolean
  status: 'disabled' | 'no_project' | 'connected' | 'incompatible' | string
  protocol_version: string
  engine_version?: string
  compatible: boolean
  project_root?: string
  project_id?: string
  session_id?: string
  revision?: number
  started_at?: string
}

export interface ApsalOperation {
  method: string
  operationId: string
  revision?: number
  previewId?: string
  undoable: boolean
}

export interface ApsalProtocolRuntime {
  getStatus(): Promise<ApsalProtocolStatus>
  chooseProject(mode: 'new' | 'open'): Promise<ApsalProjectSnapshot | null>
  call<T = unknown>(method: string, params?: Record<string, unknown>): Promise<T>
  getLinkStatus(): Promise<ApsalLinkStatus>
  onStatus(listener: (status: ApsalProtocolStatus) => void): () => void
  onSnapshot(listener: (snapshot: ApsalProjectSnapshot) => void): () => void
  onChange(listener: (event: { method: string; result: Record<string, unknown> & { snapshot?: ApsalProjectSnapshot } }) => void): () => void
  onFocus(listener: (event: { protocol_element_ids: string[]; preview_id?: string }) => void): () => void
  onLinkStatus(listener: (status: ApsalLinkStatus) => void): () => void
}

declare global {
  interface Window {
    apsalProtocol?: ApsalProtocolRuntime
  }
}
