import {
  Aperture,
  BadgeCheck,
  Check,
  Clapperboard,
  Compass,
  FolderOpen,
  GitBranch,
  Globe2,
  LayoutGrid,
  Link2,
  Link2Off,
  LocateFixed,
  MousePointer2,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Pencil,
  Plus,
  Redo2,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  Sparkles,
  Send,
  Undo2,
  X,
  ZoomIn,
  ZoomOut,
  type LucideIcon,
} from 'lucide-react'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type WheelEvent as ReactWheelEvent,
} from 'react'
import apsalIcon from './assets/apsal-icon.png'
import { CreativeLibrary } from './CreativeLibrary'
import {
  LAYERS,
  nodesToStudioView,
  projectSnapshot,
  projectWorkflowEdges,
  type ProjectedNode,
} from './protocol/projection'
import { attributeKey, buildStudioEdit, createStudioEditDraft, type StudioEditDraft } from './protocol/editor'
import { useStudioStore } from './protocol/store'
import type { ApsalLayerId, ApsalPreview } from './protocol/types'

const WORLD_WIDTH = 1540
const WORLD_HEIGHT = 900
const NODE_WIDTH = 236
const NODE_HEIGHT = 112
const LEFT_MIN = 232
const LEFT_MAX = 360
const RIGHT_MIN = 320
const RIGHT_MAX = 520

type RightTab = 'properties' | 'agent'
type ResizeSide = 'left' | 'right'
type CanvasViewport = { x: number; y: number; zoom: number }

const METHOD_LABELS: Record<string, string> = {
  'design.start': '开始设计',
  'design.authoring_mode': '切换创作模式',
  'design.propose': '创建变更提案',
  'design.commit_preview': '确认变更',
  'design.reject_preview': '拒绝变更',
  'design.commit_layer': '确认层',
  'design.finalize': '最终化主题',
  'finalize_theme': '最终化主题',
  'project.undo': '撤销操作',
  'generation.start': 'Codex 开始正式生成',
  'generation.record': 'Codex 记录生成结果',
  'qa.record': '记录视觉 QA',
}

const LAYER_ICONS: Record<ApsalLayerId, LucideIcon> = {
  direction: Compass,
  worldbuilding: Globe2,
  narrative: Clapperboard,
  image: Aperture,
  delivery: BadgeCheck,
}

function layerLabel(layer: ApsalLayerId): string {
  return LAYERS.find((item) => item.id === layer)?.label ?? layer
}

function statusLabel(status: string): string {
  if (status === 'confirmed') return '已确认'
  if (status === 'preview') return '待确认'
  if (status === 'pending') return '待处理'
  if (status === 'proposed') return '草稿'
  return status
}

function studioTypeLabel(studioType: string): string {
  const labels: Record<string, string> = {
    global_control: '全局控制',
    character: '人物元素',
    scene: '场景元素',
    styling: '造型元素',
    custom_prompt: '创作元素',
    generate_container: '生成容器',
    camera: '摄影元素',
    light: '灯光元素',
    postprocess: '后期元素',
  }
  return labels[studioType] ?? '创作元素'
}

function studioToneClass(studioType: string): string {
  return `tone-${studioType.replace(/_/g, '-')}`
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value))
}

function EmptyCanvas({ hasProject, hasSession }: { hasProject: boolean; hasSession: boolean }) {
  const busy = useStudioStore((state) => state.busy)
  const chooseProject = useStudioStore((state) => state.chooseProject)

  return (
    <div className="empty-canvas">
      <div className="empty-aperture"><Aperture aria-hidden="true" /></div>
      <span className="eyebrow">虚拟摄影工作台</span>
      <h2>{!hasProject ? '打开一个 APSAL 片场' : !hasSession ? '片场已经就位' : '等待工作流元素'}</h2>
      <p>
        {!hasProject
          ? '选择已有项目，或新建一个由 Codex 与 Studio 共同使用的 APSAL 项目。'
          : !hasSession
            ? '回到 Codex，用 APSAL 插件开始创作；工作流会投影到这里。'
            : 'Codex 创建元素后，五层工作流节点会出现在画布中。'}
      </p>
      {!hasProject && (
        <div className="empty-actions">
          <button type="button" className="button-primary" disabled={busy} onClick={() => void chooseProject('open')}>
            <FolderOpen aria-hidden="true" />打开项目
          </button>
          <button type="button" className="button-ghost" disabled={busy} onClick={() => void chooseProject('new')}>
            <Plus aria-hidden="true" />新建项目
          </button>
        </div>
      )}
    </div>
  )
}

function ProjectPanel() {
  const snapshot = useStudioStore((state) => state.snapshot)
  const status = useStudioStore((state) => state.status)
  const busy = useStudioStore((state) => state.busy)
  const chooseProject = useStudioStore((state) => state.chooseProject)
  const refresh = useStudioStore((state) => state.refresh)
  const automatic = snapshot?.session?.authoring_mode === 'automatic'

  return (
    <div className="panel-content left-content">
      <section className="projection-note">
        <div className="projection-icon"><GitBranch aria-hidden="true" /></div>
        <div>
          <strong>APSAL 协议投影</strong>
          <p>五层与十三个角色由 Engine 管理；Studio 的语义修改会作为 revision 绑定提案发送给 Codex。</p>
        </div>
      </section>

      <section className="panel-section project-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">当前项目</span>
            <h2>当前片场</h2>
          </div>
          <span className={`status-dot ${status?.running ? 'online' : ''}`} title={status?.running ? 'Engine 在线' : 'Engine 未启动'} />
        </div>
        <div className="project-actions">
          <button type="button" disabled={busy} onClick={() => void chooseProject('new')}><Plus aria-hidden="true" />新建</button>
          <button type="button" disabled={busy} onClick={() => void chooseProject('open')}><FolderOpen aria-hidden="true" />打开</button>
          <button type="button" disabled={busy || !snapshot} onClick={() => void refresh()}><RefreshCw aria-hidden="true" />刷新</button>
        </div>
        {snapshot ? (
          <div className="project-meta">
            <strong title={snapshot.project.project_id}>{snapshot.project.project_id}</strong>
            <div className={`authoring-mode-chip ${automatic ? 'automatic' : 'guided'}`} aria-label={`创作模式：${automatic ? '全自动' : '逐步确认'}`}>
              {automatic ? <Sparkles aria-hidden="true" /> : <LayoutGrid aria-hidden="true" />}
              <span>{automatic ? '全自动创作' : '逐步确认'}</span>
            </div>
            <span>项目版本 {snapshot.revision}</span>
            <span>引擎 {snapshot.engine_version} · 协议 {snapshot.protocol_version}</span>
            <span title={snapshot.project_root}>{snapshot.project_root}</span>
          </div>
        ) : (
          <p className="muted">仅支持 APSAL 0.15 项目目录。</p>
        )}
      </section>

      <section className="panel-section layers-section">
        <div className="section-heading compact">
          <span className="eyebrow">创作流程</span>
          <span className="section-count">05</span>
        </div>
        <div className="layer-list">
          {LAYERS.map((layer, index) => {
            const layerStatus = snapshot?.session?.layers[layer.id]?.status ?? 'pending'
            const Icon = LAYER_ICONS[layer.id]
            return (
              <div className={`layer-item ${layerStatus}`} key={layer.id}>
                <span className="layer-icon"><Icon aria-hidden="true" /></span>
                <div>
                  <strong>{String(index + 1).padStart(2, '0')} · {layer.label}</strong>
                  <span>{layer.short}</span>
                </div>
                <em>{statusLabel(layerStatus)}</em>
              </div>
            )
          })}
        </div>
      </section>

      <section className="panel-section workflow-note">
        <span className="eyebrow">使用方式</span>
        <p>{automatic ? 'Codex 已自动完成五层设计与打包；你仍可查看全部元素和最终状态。' : 'Codex 与 Studio 共享同一项目内核。你可以在属性面板编辑，再发送给 Codex 继续确认或调整。'}</p>
      </section>
    </div>
  )
}

function PreviewCard({ preview }: { preview: ApsalPreview }) {
  const busy = useStudioStore((state) => state.busy)
  const snapshot = useStudioStore((state) => state.snapshot)
  const confirmPreview = useStudioStore((state) => state.confirmPreview)
  const rejectPreview = useStudioStore((state) => state.rejectPreview)
  const focusElements = useStudioStore((state) => state.focusElements)
  const current = preview.status === 'pending' && snapshot?.revision === preview.base_revision
  const fromStudio = preview.origin === 'studio'
  const changedCount = preview.changes?.length ?? preview.elements.length

  return (
    <article className={`preview-card ${current ? '' : 'stale'}`}>
      <div className="preview-heading">
        <div><Sparkles aria-hidden="true" /><strong>{layerLabel(preview.layer)}</strong><small>{fromStudio ? '来自 Studio' : '来自 Codex'}</small></div>
        <span>{current ? `r${preview.base_revision}` : '已过期'}</span>
      </div>
      <p>{current ? (preview.summary || `${fromStudio ? 'Studio' : 'Codex'} 提议修改 ${changedCount} 项。`) : '项目 revision 已变化，请拒绝这条旧提案后重新编辑。'}</p>
      {preview.invalidates_if_applied.length > 0 && current && (
        <div className="impact">影响下游：{preview.invalidates_if_applied.map(layerLabel).join('、')}</div>
      )}
      <div className="preview-actions">
        <button type="button" onClick={() => focusElements(preview.elements.map((item) => item.protocol_element_id))}><LocateFixed aria-hidden="true" />定位</button>
        {fromStudio ? (
          <button type="button" className="accept" disabled><Link2 aria-hidden="true" />等待 Codex</button>
        ) : (
          <button type="button" className="accept" disabled={busy || !current || snapshot?.read_only} onClick={() => void confirmPreview(preview)}><Check aria-hidden="true" />确认</button>
        )}
        <button type="button" className="reject" disabled={busy || snapshot?.read_only} onClick={() => void rejectPreview(preview)}><X aria-hidden="true" />{fromStudio && current ? '撤回' : current ? '拒绝' : '清除'}</button>
      </div>
    </article>
  )
}

function ElementInspector({ selected }: { selected?: ProjectedNode }) {
  const busy = useStudioStore((state) => state.busy)
  const snapshot = useStudioStore((state) => state.snapshot)
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const previews = useStudioStore((state) => state.previews)
  const proposeElementChange = useStudioStore((state) => state.proposeElementChange)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<StudioEditDraft | null>(null)
  const editResult = useMemo(() => {
    if (!selected || !draft) return { value: null, error: '' }
    try {
      return { value: buildStudioEdit(selected, draft), error: '' }
    } catch (error) {
      return { value: null, error: error instanceof Error ? error.message : String(error) }
    }
  }, [draft, selected])

  useEffect(() => {
    setEditing(false)
    setDraft(selected ? createStudioEditDraft(selected) : null)
  }, [selected?.id])

  if (!selected) {
    return (
      <div className="inspector-empty">
        <span><MousePointer2 aria-hidden="true" /></span>
        <strong>选择一个工作流节点</strong>
        <p>这里可以查看语义与 QA，也可以把属性修改发送给 Codex。</p>
      </div>
    )
  }

  const Icon = LAYER_ICONS[selected.layerId]
  const hasCurrentPreview = previews.some((preview) => preview.status === 'pending' && preview.base_revision === snapshot?.revision)
  const priorLayersReady = LAYERS.slice(0, LAYERS.findIndex((layer) => layer.id === selected.layerId))
    .every((layer) => snapshot?.session?.layers[layer.id]?.status === 'confirmed')
  const themeIsEditable = !['ready', 'generating', 'completed', 'partial'].includes(snapshot?.session?.state ?? '')
  const canEdit = !selected.ghost && !snapshot?.read_only && Boolean(linkStatus?.connected) && !hasCurrentPreview && priorLayersReady && themeIsEditable
  const beginEdit = () => {
    setDraft(createStudioEditDraft(selected))
    setEditing(true)
  }
  const submitEdit = async () => {
    if (!editResult.value || editResult.value.changes.length === 0) return
    const sent = await proposeElementChange({
      layer: selected.layerId,
      roleId: selected.roleId,
      label: selected.label,
      decision: editResult.value.decision,
      changeCount: editResult.value.changes.length,
    })
    if (sent) setEditing(false)
  }
  return (
    <div className="element-inspector">
      <header className="element-header">
        <span className="element-icon"><Icon aria-hidden="true" /></span>
        <div>
          <span>创作元素 · {layerLabel(selected.layerId)}</span>
          <h2>{selected.label}</h2>
        </div>
        <div className="element-header-actions">
          <em className={selected.ghost ? 'ghost-label' : ''}>{selected.ghost ? '待确认' : statusLabel(selected.status)}</em>
          {!editing && <button type="button" className="edit-element-button" disabled={busy || !canEdit} title={!linkStatus?.connected ? '请先从 Codex 联动 Studio' : hasCurrentPreview ? '请先处理待确认变更' : !priorLayersReady ? '请先确认前面的创作层' : !themeIsEditable ? '已最终化主题需要创建新版本' : '编辑属性'} onClick={beginEdit}><Pencil aria-hidden="true" />编辑</button>}
        </div>
      </header>
      {editing && draft ? (
        <form className="element-edit-form" onSubmit={(event) => { event.preventDefault(); void submitEdit() }}>
          <label className="edit-field">
            <span>元素意图</span>
            <textarea rows={5} value={draft.intent} onChange={(event) => setDraft({ ...draft, intent: event.target.value })} />
          </label>
          {selected.attributes.map((attribute) => (
            <label className="edit-field" key={attribute.id}>
              <span>{attribute.name}</span>
              <textarea rows={typeof attribute.raw_value === 'object' ? 4 : 2} value={draft.values[attributeKey(attribute)] ?? ''} onChange={(event) => setDraft({ ...draft, values: { ...draft.values, [attributeKey(attribute)]: event.target.value } })} />
            </label>
          ))}
          {editResult.error && <p className="edit-error" role="alert">{editResult.error}</p>}
          {editResult.value && editResult.value.changes.length > 0 && (
            <section className="edit-diff" aria-label="修改摘要">
              <div className="block-heading"><span>将发送给 Codex</span><span>{editResult.value.changes.length} 项</span></div>
              {editResult.value.changes.map((change) => <div key={change.field}><strong>{change.label}</strong><span>{change.before || '空'} → {change.after || '空'}</span></div>)}
            </section>
          )}
          <p className="edit-help">列表或结构属性请保持 JSON 格式。发送后不会直接覆盖项目，而是进入双方共享的待处理变更。</p>
          <div className="edit-actions">
            <button type="button" onClick={() => { setEditing(false); setDraft(createStudioEditDraft(selected)) }}>取消</button>
            <button type="submit" className="button-primary" disabled={busy || Boolean(editResult.error) || !editResult.value?.changes.length}><Send aria-hidden="true" />发送给 Codex</button>
          </div>
        </form>
      ) : (
        <>
          <section className="read-only-block">
            <div className="block-heading"><span>元素意图</span><span>项目语义</span></div>
            <p>{selected.intent || '尚未定义'}</p>
          </section>
          {selected.attributes.length > 0 && (
            <section className="attribute-section">
              <div className="block-heading"><span>属性</span><span>{selected.attributes.length}</span></div>
              <dl>
                {selected.attributes.map((attribute) => (
                  <div className="attribute" key={attribute.id}>
                    <dt>{attribute.name}</dt>
                    <dd>{attribute.value}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
        </>
      )}
      {selected.mustPreserve.length > 0 && <div className="detail-list"><strong>必须保持</strong>{selected.mustPreserve.map((item) => <span key={item}>{item}</span>)}</div>}
      {selected.qaExpectations.length > 0 && <div className="detail-list qa"><strong>视觉 QA</strong>{selected.qaExpectations.map((item) => <span key={item}>{item}</span>)}</div>}
      {!editing && <p className="readonly-note">{!linkStatus?.connected ? '请从 Codex 插件联动 Studio 后编辑。' : hasCurrentPreview ? '当前有待处理变更，请先到 Agent 联动中确认或拒绝。' : !priorLayersReady ? '请先确认前面的创作层，再编辑这里。' : !themeIsEditable ? '当前主题已最终化或进入生成，请创建新版本后修改。' : '编辑会创建 revision 绑定提案，不会产生第二份语义状态。'}</p>}
    </div>
  )
}

function CodexLinkPanel() {
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const snapshot = useStudioStore((state) => state.snapshot)
  const studioUpdates = useStudioStore((state) => state.previews).filter((preview) => preview.origin === 'studio')

  return (
    <section className="link-card">
      <div className="link-heading">
        <span className={`link-icon ${linkStatus?.connected ? 'connected' : ''}`}>
          {linkStatus?.connected ? <Link2 aria-hidden="true" /> : <Link2Off aria-hidden="true" />}
        </span>
        <div>
          <span className="eyebrow">CODEX 联动</span>
          <h2>{linkStatus?.connected ? 'Codex 已连接' : '等待 Codex 启动'}</h2>
        </div>
        <span className="link-origin">由插件启动</span>
      </div>
      <div className={`connection-state ${linkStatus?.connected ? 'connected' : ''}`}>
        <span className="pulse" />
        {linkStatus?.connected ? '正在联动当前 APSAL 项目' : '单独打开 Studio 不会连接 Codex'}
      </div>
      <p>{linkStatus?.connected ? 'Codex 插件正通过本机认证桥访问当前项目。它不能代理任意路径，也不能绕过协议 revision。' : '请在 Codex 中打开 APSAL 插件并开始创作；选择“打开并联动 APSAL Studio”后，插件会自动打开并绑定此界面。'}</p>
      <div className="link-project">
        <div><span>绑定项目</span><strong>{snapshot?.project.project_id ?? '未选择'}</strong></div>
        <em>{studioUpdates.length ? `${studioUpdates.length} 条已发往 Codex` : '双方已同步'}</em>
      </div>
    </section>
  )
}

function OperationsPanel() {
  const operations = useStudioStore((state) => state.operations)
  const busy = useStudioStore((state) => state.busy)
  const undoOperation = useStudioStore((state) => state.undoOperation)

  return (
    <section className="operations-section">
      <div className="section-heading compact">
        <span className="eyebrow">最近操作</span>
        <span className="section-count">{operations.length}</span>
      </div>
      {operations.length ? (
        <div className="operation-list">
          {operations.map((operation) => (
            <div className="operation" key={operation.operationId}>
              <div><strong>{METHOD_LABELS[operation.method] ?? operation.method}</strong><span>revision {operation.revision ?? '?'}</span></div>
              {operation.undoable && !['project.undo', 'design.propose'].includes(operation.method) && (
                <button type="button" title="撤销这次操作" aria-label={`撤销${METHOD_LABELS[operation.method] ?? operation.method}`} disabled={busy} onClick={() => void undoOperation(operation.operationId)}><Undo2 aria-hidden="true" /></button>
              )}
            </div>
          ))}
        </div>
      ) : <p className="muted">操作记录会在 Codex 修改项目后显示。</p>}
    </section>
  )
}

function AgentPanel() {
  const previews = useStudioStore((state) => state.previews)

  return (
    <div className="agent-panel">
      <CodexLinkPanel />
      <section className="pending-section">
        <div className="section-heading compact">
          <span className="eyebrow">待确认变更</span>
          <span className="section-count warm">{previews.length}</span>
        </div>
        {previews.length ? previews.map((preview) => <PreviewCard key={preview.preview_id} preview={preview} />) : <p className="muted">双方没有待处理变更。</p>}
      </section>
      <OperationsPanel />
    </div>
  )
}

function RightPanel({ selected, tab, setTab }: { selected?: ProjectedNode; tab: RightTab; setTab: (tab: RightTab) => void }) {
  const previews = useStudioStore((state) => state.previews)

  return (
    <div className="panel-content right-content">
      <div className="right-tabs" role="tablist" aria-label="右侧面板">
        <button type="button" role="tab" aria-selected={tab === 'properties'} className={tab === 'properties' ? 'active' : ''} onClick={() => setTab('properties')}>
          <LayoutGrid aria-hidden="true" />属性
        </button>
        <button type="button" role="tab" aria-selected={tab === 'agent'} className={tab === 'agent' ? 'active' : ''} onClick={() => setTab('agent')}>
          <Sparkles aria-hidden="true" />Agent 联动{previews.length > 0 && <span>{previews.length}</span>}
        </button>
      </div>
      <div className="right-tab-content" role="tabpanel">
        {tab === 'properties' ? <ElementInspector selected={selected} /> : <AgentPanel />}
      </div>
    </div>
  )
}

function ProtocolCanvas({
  nodes,
  setNodes,
  viewport,
  setViewport,
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
  onAutoLayout,
  onInspect,
}: {
  nodes: ProjectedNode[]
  setNodes: (nodes: ProjectedNode[]) => void
  viewport: CanvasViewport
  setViewport: (viewport: CanvasViewport) => void
  leftOpen: boolean
  rightOpen: boolean
  onToggleLeft: () => void
  onToggleRight: () => void
  onAutoLayout: () => void
  onInspect: () => void
}) {
  const snapshot = useStudioStore((state) => state.snapshot)
  const selectedElementId = useStudioStore((state) => state.selectedElementId)
  const focusElementIds = useStudioStore((state) => state.focusElementIds)
  const selectElement = useStudioStore((state) => state.selectElement)
  const saveView = useStudioStore((state) => state.saveView)
  const canvasRef = useRef<HTMLDivElement>(null)
  const drag = useRef<null |
    { kind: 'node'; id: string; startX: number; startY: number; originX: number; originY: number } |
    { kind: 'pan'; startX: number; startY: number; originX: number; originY: number }
  >(null)
  const latestNodes = useRef(nodes)
  const latestViewport = useRef(viewport)
  const persistTimer = useRef<number | null>(null)
  latestNodes.current = nodes
  latestViewport.current = viewport

  const edges = useMemo(() => projectWorkflowEdges(nodes), [nodes])

  const save = (nextNodes = latestNodes.current, nextViewport = latestViewport.current) => {
    if (!snapshot?.read_only) void saveView(nodesToStudioView(nextNodes, selectedElementId, nextViewport))
  }

  const saveSoon = (nextNodes = latestNodes.current, nextViewport = latestViewport.current) => {
    if (persistTimer.current !== null) window.clearTimeout(persistTimer.current)
    persistTimer.current = window.setTimeout(() => {
      persistTimer.current = null
      save(nextNodes, nextViewport)
    }, 180)
  }

  useEffect(() => () => {
    if (persistTimer.current !== null) window.clearTimeout(persistTimer.current)
  }, [])

  const beginDrag = (event: ReactPointerEvent, node: ProjectedNode) => {
    event.preventDefault()
    event.stopPropagation()
    selectElement(node.protocolElementId)
    onInspect()
    if (node.ghost || snapshot?.read_only) return
    drag.current = { kind: 'node', id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    event.preventDefault()
    drag.current = {
      kind: 'pan',
      startX: event.clientX,
      startY: event.clientY,
      originX: viewport.x,
      originY: viewport.y,
    }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveDrag = (event: ReactPointerEvent) => {
    if (!drag.current) return
    const current = drag.current
    if (current.kind === 'pan') {
      const nextViewport = {
        ...viewport,
        x: current.originX + event.clientX - current.startX,
        y: current.originY + event.clientY - current.startY,
      }
      latestViewport.current = nextViewport
      setViewport(nextViewport)
      return
    }
    const nextNodes = nodes.map((node) => node.id === current.id ? {
      ...node,
      x: current.originX + (event.clientX - current.startX) / viewport.zoom,
      y: current.originY + (event.clientY - current.startY) / viewport.zoom,
    } : node)
    latestNodes.current = nextNodes
    setNodes(nextNodes)
  }

  const endDrag = () => {
    if (!drag.current) return
    drag.current = null
    save()
  }

  const changeZoom = (value: number) => {
    const nextZoom = Math.max(0.45, Math.min(1.7, Number(value.toFixed(2))))
    const rect = canvasRef.current?.getBoundingClientRect()
    const localX = (rect?.width ?? 800) / 2
    const localY = (rect?.height ?? 600) / 2
    const worldX = (localX - viewport.x) / viewport.zoom
    const worldY = (localY - viewport.y) / viewport.zoom
    const nextViewport = {
      x: localX - worldX * nextZoom,
      y: localY - worldY * nextZoom,
      zoom: nextZoom,
    }
    latestViewport.current = nextViewport
    setViewport(nextViewport)
    saveSoon(nodes, nextViewport)
  }

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault()
    const rect = canvasRef.current?.getBoundingClientRect()
    if (!rect) return
    const nextZoom = Math.max(0.45, Math.min(1.7, Number((viewport.zoom - event.deltaY * 0.001).toFixed(2))))
    if (nextZoom === viewport.zoom) return
    const localX = event.clientX - rect.left
    const localY = event.clientY - rect.top
    const worldX = (localX - viewport.x) / viewport.zoom
    const worldY = (localY - viewport.y) / viewport.zoom
    const nextViewport = {
      x: localX - worldX * nextZoom,
      y: localY - worldY * nextZoom,
      zoom: nextZoom,
    }
    latestViewport.current = nextViewport
    setViewport(nextViewport)
    saveSoon(nodes, nextViewport)
  }

  const moveNodeWithKeyboard = (event: ReactKeyboardEvent, node: ProjectedNode) => {
    if (node.ghost || snapshot?.read_only || !['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return false
    event.preventDefault()
    const distance = event.shiftKey ? 32 : 8
    const next = nodes.map((item) => item.id === node.id ? {
      ...item,
      x: item.x + (event.key === 'ArrowLeft' ? -distance : event.key === 'ArrowRight' ? distance : 0),
      y: item.y + (event.key === 'ArrowUp' ? -distance : event.key === 'ArrowDown' ? distance : 0),
    } : item)
    latestNodes.current = next
    setNodes(next)
    save(next)
    return true
  }

  const moveCanvasWithKeyboard = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return
    if (event.key === '+' || event.key === '=') {
      event.preventDefault()
      changeZoom(viewport.zoom + 0.1)
      return
    }
    if (event.key === '-') {
      event.preventDefault()
      changeZoom(viewport.zoom - 0.1)
      return
    }
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return
    event.preventDefault()
    const distance = event.shiftKey ? 96 : 32
    const nextViewport = {
      ...viewport,
      x: viewport.x + (event.key === 'ArrowLeft' ? distance : event.key === 'ArrowRight' ? -distance : 0),
      y: viewport.y + (event.key === 'ArrowUp' ? distance : event.key === 'ArrowDown' ? -distance : 0),
    }
    latestViewport.current = nextViewport
    setViewport(nextViewport)
    saveSoon(nodes, nextViewport)
  }

  const edgePath = (source: ProjectedNode, target: ProjectedNode): string => {
    const horizontal = Math.abs(target.x - source.x) > Math.abs(target.y - source.y) * 0.65
    if (horizontal) {
      const x1 = source.x + NODE_WIDTH
      const y1 = source.y + NODE_HEIGHT / 2
      const x2 = target.x
      const y2 = target.y + NODE_HEIGHT / 2
      const middleX = (x1 + x2) / 2
      return `M ${x1} ${y1} C ${middleX} ${y1}, ${middleX} ${y2}, ${x2} ${y2}`
    }
    const x1 = source.x + NODE_WIDTH / 2
    const y1 = source.y + NODE_HEIGHT
    const x2 = target.x + NODE_WIDTH / 2
    const y2 = target.y
    const middleY = (y1 + y2) / 2
    return `M ${x1} ${y1} C ${x1} ${middleY}, ${x2} ${middleY}, ${x2} ${y2}`
  }

  return (
    <main className="studio-panel canvas-panel" id="protocol-canvas" tabIndex={-1}>
      <div className="canvas-toolbar">
        <div className="canvas-title">
          <button type="button" className="icon-button" title={leftOpen ? '收起左栏' : '展开左栏'} aria-label={leftOpen ? '收起左栏' : '展开左栏'} onClick={onToggleLeft}>
            {leftOpen ? <PanelLeftClose aria-hidden="true" /> : <PanelLeftOpen aria-hidden="true" />}
          </button>
          <div>
            <strong>{snapshot ? `APSAL 项目 · ${snapshot.project.project_id}` : '工作流画布 3.1'}</strong>
            <span>{snapshot ? `原版卡片画布 · 项目版本 ${snapshot.revision}` : '方向 / 世界 / 叙事 / 影像 / 交付'}</span>
          </div>
        </div>
        <div className="canvas-actions">
          <button type="button" className="icon-button" title="撤销最近的可撤销操作请在右侧操作记录中选择" aria-label="查看撤销提示" disabled><Undo2 aria-hidden="true" /></button>
          <button type="button" className="icon-button" title="重做由 Codex 协议管理" aria-label="重做不可用" disabled><Redo2 aria-hidden="true" /></button>
          <button type="button" className="toolbar-button" disabled={!snapshot || !nodes.length} onClick={onAutoLayout}><RotateCcw aria-hidden="true" />自动布局</button>
          <span className="canvas-stat"><strong>{nodes.length}</strong> 节点</span>
          <span className="canvas-stat"><strong>5</strong> 层</span>
          <div className="zoom-controls" aria-label="画布缩放">
            <button type="button" title="缩小" aria-label="缩小画布" onClick={() => changeZoom(viewport.zoom - 0.1)}><ZoomOut aria-hidden="true" /></button>
            <span>{Math.round(viewport.zoom * 100)}%</span>
            <button type="button" title="放大" aria-label="放大画布" onClick={() => changeZoom(viewport.zoom + 0.1)}><ZoomIn aria-hidden="true" /></button>
          </div>
          <button type="button" className="icon-button" title={rightOpen ? '收起右栏' : '展开右栏'} aria-label={rightOpen ? '收起右栏' : '展开右栏'} onClick={onToggleRight}>
            {rightOpen ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}
          </button>
        </div>
      </div>
      <div className="canvas-body">
        <div className="canvas-stage-label"><span>阶段 01</span><strong>卡片工作流</strong></div>
        <div
          ref={canvasRef}
          className={`canvas-scroll ${drag.current?.kind === 'pan' ? 'panning' : ''}`}
          tabIndex={0}
          aria-label="工作流卡片画布；拖动空白处平移，滚轮缩放，方向键浏览"
          onPointerDown={beginPan}
          onPointerMove={moveDrag}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
          onWheel={handleWheel}
          onKeyDown={moveCanvasWithKeyboard}
        >
          {!nodes.length ? (
            <EmptyCanvas hasProject={Boolean(snapshot)} hasSession={Boolean(snapshot?.session)} />
          ) : (
            <div
              className="world"
              style={{
                width: WORLD_WIDTH,
                height: WORLD_HEIGHT,
                transform: `translate(${viewport.x}px, ${viewport.y}px) scale(${viewport.zoom})`,
              }}
            >
                <svg className="workflow-edges" width={WORLD_WIDTH} height={WORLD_HEIGHT} aria-hidden="true">
                  {edges.map((edge) => (
                    <g key={edge.id}>
                      <path d={edgePath(edge.source, edge.target)} />
                      <circle cx={edge.target.x} cy={edge.target.y + NODE_HEIGHT / 2} r="3" />
                    </g>
                  ))}
                </svg>
                {nodes.map((node) => {
                  const selected = selectedElementId === node.protocolElementId
                  const focused = focusElementIds.includes(node.protocolElementId)
                  const Icon = LAYER_ICONS[node.layerId]
                  return (
                    <div
                      className={`protocol-node ${studioToneClass(node.studioType)} ${node.status} ${node.ghost ? 'ghost' : ''} ${selected ? 'selected' : ''} ${focused ? 'focused' : ''}`}
                      key={node.id}
                      style={{ left: node.x, top: node.y }}
                      role="button"
                      tabIndex={0}
                      aria-label={`${node.label}，${node.ghost ? '待确认预览' : statusLabel(node.status)}`}
                      onPointerDown={(event) => beginDrag(event, node)}
                      onClick={() => { selectElement(node.protocolElementId); onInspect() }}
                      onKeyDown={(event) => {
                        if (moveNodeWithKeyboard(event, node)) return
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          selectElement(node.protocolElementId)
                          onInspect()
                        }
                      }}
                    >
                      <div className="node-card-header">
                        <span className="node-icon"><Icon aria-hidden="true" /></span>
                        <div className="node-heading">
                          <h3>{node.label}</h3>
                          <span>{layerLabel(node.layerId)} · {studioTypeLabel(node.studioType)}</span>
                        </div>
                        <em>{statusLabel(node.status)}</em>
                      </div>
                      <p>{node.intent || '等待 Codex 定义该元素'}</p>
                      <div className="node-footer">
                        <span>属性 {node.attributes.length}</span>
                        <span>约束 {node.mustPreserve.length + node.qaExpectations.length}</span>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </div>
    </main>
  )
}

export function App() {
  const available = useStudioStore((state) => state.available)
  const initialize = useStudioStore((state) => state.initialize)
  const snapshot = useStudioStore((state) => state.snapshot)
  const status = useStudioStore((state) => state.status)
  const view = useStudioStore((state) => state.view)
  const previews = useStudioStore((state) => state.previews)
  const selectedElementId = useStudioStore((state) => state.selectedElementId)
  const error = useStudioStore((state) => state.error)
  const busy = useStudioStore((state) => state.busy)
  const clearError = useStudioStore((state) => state.clearError)
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const syncMessage = useStudioStore((state) => state.syncMessage)
  const clearSyncMessage = useStudioStore((state) => state.clearSyncMessage)
  const saveView = useStudioStore((state) => state.saveView)
  const [nodes, setNodes] = useState<ProjectedNode[]>([])
  const [viewport, setViewport] = useState<CanvasViewport>({ x: 30, y: 36, zoom: 0.72 })
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [leftWidth, setLeftWidth] = useState(260)
  const [rightWidth, setRightWidth] = useState(410)
  const [rightTab, setRightTab] = useState<RightTab>('properties')
  const [screen, setScreen] = useState<'library' | 'studio'>('library')
  const [notice, setNotice] = useState('')
  const [migrationBusy, setMigrationBusy] = useState(false)
  const [migrationError, setMigrationError] = useState('')
  const resizeRef = useRef<{ side: ResizeSide; startX: number; startWidth: number } | null>(null)

  useEffect(() => { void initialize() }, [initialize])
  useEffect(() => {
    setNodes(snapshot ? projectSnapshot(snapshot, view) : [])
    setViewport({
      x: Number(view?.viewport?.x ?? 30),
      y: Number(view?.viewport?.y ?? 36),
      zoom: Number(view?.viewport?.zoom ?? 0.72),
    })
  }, [snapshot, view])
  useEffect(() => {
    if (previews.length > 0) {
      setRightOpen(true)
      setRightTab('agent')
    }
  }, [previews.length])
  useEffect(() => {
    if (!syncMessage) return
    const timer = window.setTimeout(clearSyncMessage, 3200)
    return () => window.clearTimeout(timer)
  }, [clearSyncMessage, syncMessage])

  useEffect(() => {
    const onMove = (event: PointerEvent) => {
      const current = resizeRef.current
      if (!current) return
      const delta = event.clientX - current.startX
      if (current.side === 'left') setLeftWidth(clamp(current.startWidth + delta, LEFT_MIN, LEFT_MAX))
      else setRightWidth(clamp(current.startWidth - delta, RIGHT_MIN, RIGHT_MAX))
    }
    const onUp = () => {
      resizeRef.current = null
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
    return () => {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
  }, [])

  const selected = useMemo(
    () => nodes.find((node) => node.protocolElementId === selectedElementId && !node.ghost)
      ?? nodes.find((node) => node.protocolElementId === selectedElementId),
    [nodes, selectedElementId],
  )

  const startResize = useCallback((side: ResizeSide, event: ReactPointerEvent<HTMLDivElement>) => {
    event.preventDefault()
    resizeRef.current = { side, startX: event.clientX, startWidth: side === 'left' ? leftWidth : rightWidth }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }, [leftWidth, rightWidth])

  const resizeWithKeyboard = useCallback((side: ResizeSide, event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return
    event.preventDefault()
    const step = event.shiftKey ? 32 : 8
    if (side === 'left') {
      setLeftWidth((width) => clamp(width + (event.key === 'ArrowRight' ? step : -step), LEFT_MIN, LEFT_MAX))
    } else {
      setRightWidth((width) => clamp(width + (event.key === 'ArrowLeft' ? step : -step), RIGHT_MIN, RIGHT_MAX))
    }
  }, [])

  const autoLayout = useCallback(() => {
    if (!snapshot) return
    const nextViewport = { x: 30, y: 36, zoom: 0.72 }
    const nextNodes = projectSnapshot(snapshot)
    setNodes(nextNodes)
    setViewport(nextViewport)
    if (!snapshot.read_only) void saveView(nodesToStudioView(nextNodes, selectedElementId, nextViewport))
    setNotice('画布已恢复为原版卡片布局')
    window.setTimeout(() => setNotice(''), 2600)
  }, [saveView, selectedElementId, snapshot])

  const migrateProject = useCallback(async () => {
    if (!snapshot || !window.apsalProtocol) return
    const confirmed = window.confirm(`迁移预览\n\n来源：${snapshot.project_root}\n版本：APSAL 0.15 → 0.16\n方式：复制到 ~/APSAL Projects/ 后迁移\n\n原项目不会被修改，并将继续以只读方式保留。确认创建迁移副本？`)
    if (!confirmed) return
    setMigrationBusy(true)
    setMigrationError('')
    try {
      await window.apsalProtocol.migrateCurrentProject()
      setNotice('迁移副本已创建并打开；原 0.15 项目保持不变。')
    } catch (error) {
      setMigrationError(error instanceof Error ? error.message : String(error))
    } finally {
      setMigrationBusy(false)
    }
  }, [snapshot])

  if (!available) {
    return (
      <div className="desktop-required">
        <div className="brand-mark"><img src={apsalIcon} alt="" /></div>
        <span className="eyebrow">虚拟摄影工作台</span>
        <h1>APSAL Studio 0.3.0</h1>
        <p>此界面只在 APSAL Studio Desktop 中运行，用于连接 Codex APSAL 插件。</p>
      </div>
    )
  }

  const gridTemplateColumns = `${leftOpen ? `${leftWidth}px` : '0px'} 8px minmax(540px, 1fr) 8px ${rightOpen ? `${rightWidth}px` : '0px'}`

  return (
    <div className="app-shell">
      <a className="skip-link" href={screen === 'library' ? '#creative-library' : '#protocol-canvas'}>跳到主要内容</a>
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark"><img src={apsalIcon} alt="" /></div>
          <div className="brand-copy"><strong>APSAL Studio</strong><span><Aperture aria-hidden="true" />虚拟摄影工作台<i />阶段 01</span></div>
        </div>
        <div className="scene-field" title={snapshot?.project_root}>
          <span>当前项目 · 当前片场</span>
          <strong>{snapshot?.project.name ?? snapshot?.project.project_id ?? '未选择 APSAL 项目'}</strong>
        </div>
        <div className="header-stats">
          <span className={`topbar-stat ${status?.running ? 'online' : ''}`}><ScanSearch aria-hidden="true" />{status?.running ? 'Engine 在线' : 'Engine 启动中'}</span>
          <span className="topbar-stat"><GitBranch aria-hidden="true" />r{snapshot?.revision ?? '—'}</span>
          <span className={`topbar-stat ${linkStatus?.connected ? 'online' : ''}`}>{linkStatus?.connected ? <Link2 aria-hidden="true" /> : <Link2Off aria-hidden="true" />}{linkStatus?.connected ? 'Codex 已连接' : 'Codex 未连接'}</span>
          <span className="version-stat">0.3.0 / 0.16.0</span>
        </div>
        <nav className="top-navigation" aria-label="Studio 主导航">
          <button type="button" className={screen === 'library' ? 'active' : ''} onClick={() => setScreen('library')}><LayoutGrid />项目库</button>
          <button type="button" className={screen === 'studio' ? 'active' : ''} onClick={() => setScreen('studio')}><GitBranch />工作流</button>
        </nav>
      </header>
      {screen === 'library' ? <CreativeLibrary onOpenProject={() => setScreen('studio')} /> : <>
        {snapshot?.read_only && <div className="compatibility-banner"><span>只读模式：{snapshot.compatibility_error || '协议版本不兼容，请预览并复制迁移到 APSAL 0.16。'}</span><button type="button" disabled={migrationBusy} onClick={() => void migrateProject()}>{migrationBusy ? <RefreshCw className="spin" /> : <GitBranch />}预览并复制迁移</button>{migrationError && <em role="alert">{migrationError}</em>}</div>}
        <nav className="project-pipeline-strip" aria-label="当前项目流水线">
          {['参考图', '分析', '设计', '生成', 'QA', 'Skill', '分享'].map((label, index) => <span key={label} className={snapshot?.session ? (index < 3 ? 'complete' : index === 3 ? 'current' : '') : index === 0 ? 'current' : ''}><i>{index + 1}</i>{label}</span>)}
        </nav>
        <div className="workspace-frame">
        <div className="workspace-grid" style={{ gridTemplateColumns }}>
          <aside className={`studio-panel side-panel ${leftOpen ? '' : 'collapsed'}`} aria-hidden={!leftOpen}><ProjectPanel /></aside>
          <div
            className={`resize-handle ${leftOpen ? '' : 'disabled'}`}
            role="separator"
            aria-orientation="vertical"
            aria-label="调整左侧栏宽度"
            aria-valuemin={LEFT_MIN}
            aria-valuemax={LEFT_MAX}
            aria-valuenow={leftWidth}
            tabIndex={leftOpen ? 0 : -1}
            onPointerDown={(event) => leftOpen && startResize('left', event)}
            onKeyDown={(event) => leftOpen && resizeWithKeyboard('left', event)}
          ><span /></div>
          <ProtocolCanvas
            nodes={nodes}
            setNodes={setNodes}
            viewport={viewport}
            setViewport={setViewport}
            leftOpen={leftOpen}
            rightOpen={rightOpen}
            onToggleLeft={() => setLeftOpen((value) => !value)}
            onToggleRight={() => setRightOpen((value) => !value)}
            onAutoLayout={autoLayout}
            onInspect={() => { setRightOpen(true); setRightTab('properties') }}
          />
          <div
            className={`resize-handle ${rightOpen ? '' : 'disabled'}`}
            role="separator"
            aria-orientation="vertical"
            aria-label="调整右侧栏宽度"
            aria-valuemin={RIGHT_MIN}
            aria-valuemax={RIGHT_MAX}
            aria-valuenow={rightWidth}
            tabIndex={rightOpen ? 0 : -1}
            onPointerDown={(event) => rightOpen && startResize('right', event)}
            onKeyDown={(event) => rightOpen && resizeWithKeyboard('right', event)}
          ><span /></div>
          <aside className={`studio-panel side-panel ${rightOpen ? '' : 'collapsed'}`} aria-hidden={!rightOpen}><RightPanel selected={selected} tab={rightTab} setTab={setRightTab} /></aside>
        </div>
        </div>
      </>}
      {busy && <div className="working-indicator" role="status" aria-live="polite"><RefreshCw aria-hidden="true" />APSAL 正在处理</div>}
      {(notice || syncMessage) && <div className="notice-toast" role="status" aria-live="polite"><BadgeCheck aria-hidden="true" />{notice || syncMessage}</div>}
      {error && <button type="button" className="error-toast" role="alert" aria-live="assertive" onClick={clearError}>{error}<span>关闭</span></button>}
    </div>
  )
}
