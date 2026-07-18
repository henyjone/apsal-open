import { create } from 'zustand'
import type {
  ApsalLinkStatus,
  ApsalOperation,
  ApsalPreview,
  ApsalProjectSnapshot,
  ApsalProtocolStatus,
  ApsalStudioView,
} from './types'

interface StudioState {
  available: boolean
  initialized: boolean
  busy: boolean
  error: string
  status: ApsalProtocolStatus | null
  linkStatus: ApsalLinkStatus | null
  snapshot: ApsalProjectSnapshot | null
  view: ApsalStudioView | null
  previews: ApsalPreview[]
  operations: ApsalOperation[]
  focusElementIds: string[]
  selectedElementId: string | null
  initialize: () => Promise<void>
  chooseProject: (mode: 'new' | 'open') => Promise<void>
  refresh: () => Promise<void>
  confirmPreview: (preview: ApsalPreview) => Promise<void>
  rejectPreview: (preview: ApsalPreview) => Promise<void>
  undoOperation: (operationId: string) => Promise<void>
  saveView: (view: Omit<ApsalStudioView, 'schema_version' | 'view_revision'>) => Promise<void>
  selectElement: (id: string | null) => void
  focusElements: (ids: string[]) => void
  clearError: () => void
}

let unsubscribers: Array<() => void> = []

function message(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function operationId(prefix: string): string {
  return `STUDIO-${prefix}-${crypto.randomUUID()}`
}

export const useStudioStore = create<StudioState>((set, get) => ({
  available: typeof window !== 'undefined' && Boolean(window.apsalProtocol),
  initialized: false,
  busy: false,
  error: '',
  status: null,
  linkStatus: null,
  snapshot: null,
  view: null,
  previews: [],
  operations: [],
  focusElementIds: [],
  selectedElementId: null,

  initialize: async () => {
    const runtime = window.apsalProtocol
    if (!runtime || get().initialized) return
    unsubscribers.forEach((unsubscribe) => unsubscribe())
    unsubscribers = [
      runtime.onStatus((status) => set({ status })),
      runtime.onLinkStatus((linkStatus) => set({ linkStatus })),
      runtime.onSnapshot((snapshot) => set({ snapshot, previews: snapshot.previews ?? [] })),
      runtime.onFocus((event) => set({ focusElementIds: event.protocol_element_ids || [], selectedElementId: event.protocol_element_ids?.[0] ?? null })),
      runtime.onChange((event) => {
        const result = event.result
        if (result.snapshot) set({ snapshot: result.snapshot, previews: result.snapshot.previews ?? [] })
        else void get().refresh()
        if (result.operation_id) {
          const operation: ApsalOperation = {
            method: event.method,
            operationId: String(result.operation_id),
            revision: typeof result.revision === 'number' ? result.revision : undefined,
            previewId: typeof result.preview_id === 'string' ? result.preview_id : undefined,
            undoable: result.undoable !== false,
          }
          set((state) => ({ operations: [operation, ...state.operations.filter((item) => item.operationId !== operation.operationId)].slice(0, 12) }))
        }
      }),
    ]
    set({ initialized: true, busy: true, error: '' })
    try {
      const [status, linkStatus] = await Promise.all([runtime.getStatus(), runtime.getLinkStatus()])
      set({ status, linkStatus })
      if (status.project_root) await get().refresh()
    } catch (error) {
      set({ error: message(error) })
    } finally {
      set({ busy: false })
    }
  },

  chooseProject: async (mode) => {
    const runtime = window.apsalProtocol
    if (!runtime) return
    set({ busy: true, error: '', previews: [], operations: [], selectedElementId: null })
    try {
      const snapshot = await runtime.chooseProject(mode)
      if (!snapshot) return
      const view = await runtime.call<ApsalStudioView>('studio.view.get')
      const [status, linkStatus] = await Promise.all([runtime.getStatus(), runtime.getLinkStatus()])
      set({ snapshot, view, previews: snapshot.previews ?? [], status, linkStatus, selectedElementId: view.selected_element_id ?? null })
    } catch (error) {
      set({ error: message(error) })
    } finally {
      set({ busy: false })
    }
  },

  refresh: async () => {
    const runtime = window.apsalProtocol
    if (!runtime || !get().status?.project_root) return
    try {
      const [snapshot, view, linkStatus] = await Promise.all([
        runtime.call<ApsalProjectSnapshot>('project.snapshot'),
        runtime.call<ApsalStudioView>('studio.view.get'),
        runtime.getLinkStatus(),
      ])
      set((state) => ({
        snapshot,
        view,
        linkStatus,
        previews: snapshot.previews ?? [],
        selectedElementId: state.selectedElementId ?? view.selected_element_id ?? null,
        error: '',
      }))
    } catch (error) {
      set({ error: message(error) })
    }
  },

  confirmPreview: async (preview) => {
    const runtime = window.apsalProtocol
    const snapshot = get().snapshot
    if (!runtime || !snapshot) return
    if (preview.status !== 'pending' || snapshot.revision !== preview.base_revision) {
      set({ error: '该变更已过期，请刷新项目后由 Codex 重新创建预览。' })
      return
    }
    set({ busy: true, error: '' })
    try {
      const result = await runtime.call<{ snapshot: ApsalProjectSnapshot }>('design.commit_preview', {
        session_id: preview.session_id,
        preview_id: preview.preview_id,
        expected_revision: preview.base_revision,
        operation_id: operationId('APPLY'),
      })
      set({ snapshot: result.snapshot, previews: result.snapshot.previews ?? [] })
    } catch (error) {
      set({ error: message(error) })
    } finally {
      set({ busy: false })
    }
  },

  rejectPreview: async (preview) => {
    const runtime = window.apsalProtocol
    const snapshot = get().snapshot
    if (!runtime || !snapshot) return
    if (preview.status !== 'pending' || snapshot.revision !== preview.base_revision) {
      set({ error: '该变更已过期，请刷新项目。' })
      return
    }
    set({ busy: true, error: '' })
    try {
      const result = await runtime.call<{ snapshot: ApsalProjectSnapshot }>('design.reject_preview', {
        session_id: preview.session_id,
        preview_id: preview.preview_id,
        expected_revision: preview.base_revision,
        operation_id: operationId('REJECT'),
      })
      set({ snapshot: result.snapshot, previews: result.snapshot.previews ?? [] })
    } catch (error) {
      set({ error: message(error) })
    } finally {
      set({ busy: false })
    }
  },

  undoOperation: async (targetOperationId) => {
    const runtime = window.apsalProtocol
    const snapshot = get().snapshot
    if (!runtime || !snapshot) return
    set({ busy: true, error: '' })
    try {
      const result = await runtime.call<{ snapshot: ApsalProjectSnapshot }>('project.undo', {
        target_operation_id: targetOperationId,
        expected_revision: snapshot.revision,
        operation_id: operationId('UNDO'),
      })
      set({ snapshot: result.snapshot, previews: result.snapshot.previews ?? [] })
    } catch (error) {
      set({ error: message(error) })
    } finally {
      set({ busy: false })
    }
  },

  saveView: async (view) => {
    const runtime = window.apsalProtocol
    const snapshot = get().snapshot
    if (!runtime || !snapshot || snapshot.read_only) return
    try {
      set({ view: await runtime.call<ApsalStudioView>('studio.view.save', { view }) })
    } catch (error) {
      set({ error: message(error) })
    }
  },

  selectElement: (id) => set({ selectedElementId: id }),
  focusElements: (ids) => set({ focusElementIds: ids, selectedElementId: ids[0] ?? null }),
  clearError: () => set({ error: '' }),
}))
