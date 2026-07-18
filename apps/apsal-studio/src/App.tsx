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
  Plus,
  Redo2,
  RefreshCw,
  RotateCcw,
  ScanSearch,
  Sparkles,
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
} from 'react'
import apsalIcon from './assets/apsal-icon.png'
import { LAYERS, nodesToStudioView, projectSnapshot, type ProjectedNode } from './protocol/projection'
import { useStudioStore } from './protocol/store'
import type { ApsalLayerId, ApsalPreview } from './protocol/types'

const WORLD_WIDTH = 1540
const WORLD_HEIGHT = 900
const LEFT_MIN = 232
const LEFT_MAX = 360
const RIGHT_MIN = 320
const RIGHT_MAX = 520

type RightTab = 'properties' | 'agent'
type ResizeSide = 'left' | 'right'

const METHOD_LABELS: Record<string, string> = {
  'design.start': '开始设计',
  'design.propose': 'Codex 提交预览',
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

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value))
}

function EmptyCanvas({ hasProject, hasSession }: { hasProject: boolean; hasSession: boolean }) {
  const busy = useStudioStore((state) => state.busy)
  const chooseProject = useStudioStore((state) => state.chooseProject)

  return (
    <div className="empty-canvas">
      <div className="empty-aperture"><Aperture aria-hidden="true" /></div>
      <span className="eyebrow">VIRTUAL SHOOT DESK</span>
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

  return (
    <div className="panel-content left-content">
      <section className="projection-note">
        <div className="projection-icon"><GitBranch aria-hidden="true" /></div>
        <div>
          <strong>APSAL 协议投影</strong>
          <p>五层与十三个角色由 Engine 管理；Studio 只保存画布位置、缩放和选中状态。</p>
        </div>
      </section>

      <section className="panel-section project-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PROJECT</span>
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
            <span>revision {snapshot.revision}</span>
            <span>Engine {snapshot.engine_version} · Protocol {snapshot.protocol_version}</span>
            <span title={snapshot.project_root}>{snapshot.project_root}</span>
          </div>
        ) : (
          <p className="muted">仅支持 APSAL 0.15 项目目录。</p>
        )}
      </section>

      <section className="panel-section layers-section">
        <div className="section-heading compact">
          <span className="eyebrow">WORKFLOW LAYERS</span>
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
        <span className="eyebrow">WORKFLOW</span>
        <p>创作对话与语义编辑在 Codex 中进行。Studio 用于观察项目、定位元素、确认预览和回看操作。</p>
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

  return (
    <article className={`preview-card ${current ? '' : 'stale'}`}>
      <div className="preview-heading">
        <div><Sparkles aria-hidden="true" /><strong>{layerLabel(preview.layer)}</strong></div>
        <span>{current ? `r${preview.base_revision}` : '已过期'}</span>
      </div>
      <p>{current ? `Codex 提议更新 ${preview.elements.length} 个元素。` : '项目 revision 已变化，需要由 Codex 重新创建预览。'}</p>
      {preview.invalidates_if_applied.length > 0 && current && (
        <div className="impact">影响下游：{preview.invalidates_if_applied.map(layerLabel).join('、')}</div>
      )}
      <div className="preview-actions">
        <button type="button" onClick={() => focusElements(preview.elements.map((item) => item.protocol_element_id))}><LocateFixed aria-hidden="true" />定位</button>
        <button type="button" className="accept" disabled={busy || !current || snapshot?.read_only} onClick={() => void confirmPreview(preview)}><Check aria-hidden="true" />确认</button>
        <button type="button" className="reject" disabled={busy || !current || snapshot?.read_only} onClick={() => void rejectPreview(preview)}><X aria-hidden="true" />拒绝</button>
      </div>
    </article>
  )
}

function ElementInspector({ selected }: { selected?: ProjectedNode }) {
  if (!selected) {
    return (
      <div className="inspector-empty">
        <span><MousePointer2 aria-hidden="true" /></span>
        <strong>选择一个工作流节点</strong>
        <p>这里显示由 APSAL Engine 管理的只读语义和 QA 约束。</p>
      </div>
    )
  }

  const Icon = LAYER_ICONS[selected.layerId]
  return (
    <div className="element-inspector">
      <header className="element-header">
        <span className="element-icon"><Icon aria-hidden="true" /></span>
        <div>
          <span>{selected.roleId} · {layerLabel(selected.layerId)}</span>
          <h2>{selected.label}</h2>
        </div>
        <em className={selected.ghost ? 'ghost-label' : ''}>{selected.ghost ? '待确认' : statusLabel(selected.status)}</em>
      </header>
      <section className="read-only-block">
        <div className="block-heading"><span>元素意图</span><span>READ ONLY</span></div>
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
      {selected.mustPreserve.length > 0 && <div className="detail-list"><strong>必须保持</strong>{selected.mustPreserve.map((item) => <span key={item}>{item}</span>)}</div>}
      {selected.qaExpectations.length > 0 && <div className="detail-list qa"><strong>视觉 QA</strong>{selected.qaExpectations.map((item) => <span key={item}>{item}</span>)}</div>}
      <p className="readonly-note">需要修改时，请在 Codex 中描述意图；Studio 不创建第二份语义状态。</p>
    </div>
  )
}

function CodexLinkPanel() {
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const busy = useStudioStore((state) => state.busy)
  const snapshot = useStudioStore((state) => state.snapshot)
  const setLinkEnabled = useStudioStore((state) => state.setLinkEnabled)

  return (
    <section className="link-card">
      <div className="link-heading">
        <span className={`link-icon ${linkStatus?.connected ? 'connected' : ''}`}>
          {linkStatus?.connected ? <Link2 aria-hidden="true" /> : <Link2Off aria-hidden="true" />}
        </span>
        <div>
          <span className="eyebrow">CODEX LINK</span>
          <h2>{linkStatus?.connected ? 'Codex 已连接' : 'Codex 联动'}</h2>
        </div>
        <button
          type="button"
          className={`switch ${linkStatus?.enabled ? 'enabled' : ''}`}
          aria-label={linkStatus?.enabled ? '关闭 Codex 联动' : '开启 Codex 联动'}
          aria-pressed={linkStatus?.enabled ?? false}
          disabled={busy}
          onClick={() => void setLinkEnabled(!linkStatus?.enabled)}
        >
          <span />
        </button>
      </div>
      <div className={`connection-state ${linkStatus?.connected ? 'connected' : ''}`}>
        <span className="pulse" />
        {linkStatus?.connected ? '正在联动当前 APSAL 项目' : linkStatus?.enabled ? '联动已开启，等待当前项目' : '联动默认关闭'}
      </div>
      <p>开启后，Codex 插件通过本机认证桥访问当前项目。它不能代理任意路径，也不能绕过协议 revision。</p>
      <div className="link-project">
        <span>绑定项目</span>
        <strong>{snapshot?.project.project_id ?? '未选择'}</strong>
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
        <span className="eyebrow">RECENT OPERATIONS</span>
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
          <span className="eyebrow">PENDING CHANGES</span>
          <span className="section-count warm">{previews.length}</span>
        </div>
        {previews.length ? previews.map((preview) => <PreviewCard key={preview.preview_id} preview={preview} />) : <p className="muted">等待 Codex 提交变更预览。</p>}
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
  zoom,
  setZoom,
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
  onAutoLayout,
  onInspect,
}: {
  nodes: ProjectedNode[]
  setNodes: (nodes: ProjectedNode[]) => void
  zoom: number
  setZoom: (zoom: number) => void
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
  const drag = useRef<null | { id: string; startX: number; startY: number; originX: number; originY: number }>(null)

  const save = (nextNodes: ProjectedNode[], nextZoom = zoom) => {
    if (!snapshot?.read_only) void saveView(nodesToStudioView(nextNodes, selectedElementId, nextZoom))
  }

  const beginDrag = (event: ReactPointerEvent, node: ProjectedNode) => {
    selectElement(node.protocolElementId)
    onInspect()
    if (node.ghost || snapshot?.read_only) return
    drag.current = { id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveDrag = (event: ReactPointerEvent) => {
    if (!drag.current) return
    const current = drag.current
    setNodes(nodes.map((node) => node.id === current.id ? {
      ...node,
      x: current.originX + (event.clientX - current.startX) / zoom,
      y: current.originY + (event.clientY - current.startY) / zoom,
    } : node))
  }

  const endDrag = () => {
    if (!drag.current) return
    drag.current = null
    save(nodes)
  }

  const changeZoom = (value: number) => {
    const next = Math.max(0.65, Math.min(1.15, Number(value.toFixed(2))))
    setZoom(next)
    save(nodes, next)
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
    setNodes(next)
    save(next)
    return true
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
            <span>{snapshot ? `单一内核投影 · revision ${snapshot.revision}` : '方向 / 世界 / 叙事 / 影像 / 交付'}</span>
          </div>
        </div>
        <div className="canvas-actions">
          <button type="button" className="icon-button" title="撤销最近的可撤销操作请在右侧操作记录中选择" aria-label="查看撤销提示" disabled><Undo2 aria-hidden="true" /></button>
          <button type="button" className="icon-button" title="重做由 Codex 协议管理" aria-label="重做不可用" disabled><Redo2 aria-hidden="true" /></button>
          <button type="button" className="toolbar-button" disabled={!snapshot || !nodes.length} onClick={onAutoLayout}><RotateCcw aria-hidden="true" />自动布局</button>
          <span className="canvas-stat"><strong>{nodes.length}</strong> 节点</span>
          <span className="canvas-stat"><strong>5</strong> 层</span>
          <div className="zoom-controls" aria-label="画布缩放">
            <button type="button" title="缩小" aria-label="缩小画布" onClick={() => changeZoom(zoom - 0.1)}><ZoomOut aria-hidden="true" /></button>
            <span>{Math.round(zoom * 100)}%</span>
            <button type="button" title="放大" aria-label="放大画布" onClick={() => changeZoom(zoom + 0.1)}><ZoomIn aria-hidden="true" /></button>
          </div>
          <button type="button" className="icon-button" title={rightOpen ? '收起右栏' : '展开右栏'} aria-label={rightOpen ? '收起右栏' : '展开右栏'} onClick={onToggleRight}>
            {rightOpen ? <PanelRightClose aria-hidden="true" /> : <PanelRightOpen aria-hidden="true" />}
          </button>
        </div>
      </div>
      <div className="canvas-body">
        <div className="canvas-stage-label"><span>STAGE 01</span><strong>PROTOCOL WORKFLOW</strong></div>
        <div className="canvas-scroll" onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
          {!nodes.length ? (
            <EmptyCanvas hasProject={Boolean(snapshot)} hasSession={Boolean(snapshot?.session)} />
          ) : (
            <div className="world-scale" style={{ width: WORLD_WIDTH * zoom, height: WORLD_HEIGHT * zoom }}>
              <div className="world" style={{ width: WORLD_WIDTH, height: WORLD_HEIGHT, transform: `scale(${zoom})` }}>
                {LAYERS.map((layer, index) => {
                  const Icon = LAYER_ICONS[layer.id]
                  return (
                    <div className="layer-column" key={layer.id} style={{ left: 24 + index * 300 }}>
                      <div><span>{String(index + 1).padStart(2, '0')}</span><Icon aria-hidden="true" /></div>
                      <strong>{layer.label}</strong>
                      <em>{layer.short}</em>
                    </div>
                  )
                })}
                {nodes.map((node) => {
                  const selected = selectedElementId === node.protocolElementId
                  const focused = focusElementIds.includes(node.protocolElementId)
                  const Icon = LAYER_ICONS[node.layerId]
                  return (
                    <div
                      className={`protocol-node ${node.status} ${node.ghost ? 'ghost' : ''} ${selected ? 'selected' : ''} ${focused ? 'focused' : ''}`}
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
                      <div className="node-topline">
                        <span className="node-role"><Icon aria-hidden="true" />{node.roleId}</span>
                        <em>{node.ghost ? 'PREVIEW' : statusLabel(node.status)}</em>
                      </div>
                      <h3>{node.label}</h3>
                      <p>{node.intent || '等待 Codex 定义该元素'}</p>
                      <div className="node-footer"><span>{layerLabel(node.layerId)}</span><strong>{node.attributes.length} 属性</strong></div>
                    </div>
                  )
                })}
              </div>
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
  const saveView = useStudioStore((state) => state.saveView)
  const [nodes, setNodes] = useState<ProjectedNode[]>([])
  const [zoom, setZoom] = useState(0.82)
  const [leftOpen, setLeftOpen] = useState(true)
  const [rightOpen, setRightOpen] = useState(true)
  const [leftWidth, setLeftWidth] = useState(260)
  const [rightWidth, setRightWidth] = useState(410)
  const [rightTab, setRightTab] = useState<RightTab>('properties')
  const [notice, setNotice] = useState('')
  const resizeRef = useRef<{ side: ResizeSide; startX: number; startWidth: number } | null>(null)

  useEffect(() => { void initialize() }, [initialize])
  useEffect(() => {
    setNodes(snapshot ? projectSnapshot(snapshot, view, previews) : [])
    setZoom(Number(view?.viewport?.zoom ?? 0.82))
  }, [snapshot, view, previews])
  useEffect(() => {
    if (previews.length > 0) {
      setRightOpen(true)
      setRightTab('agent')
    }
  }, [previews.length])

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
    const nextZoom = 0.82
    const nextNodes = projectSnapshot(snapshot, undefined, previews)
    setNodes(nextNodes)
    setZoom(nextZoom)
    if (!snapshot.read_only) void saveView(nodesToStudioView(nextNodes, selectedElementId, nextZoom))
    setNotice('画布已恢复为五层自动布局')
    window.setTimeout(() => setNotice(''), 2600)
  }, [previews, saveView, selectedElementId, snapshot])

  if (!available) {
    return (
      <div className="desktop-required">
        <div className="brand-mark"><img src={apsalIcon} alt="" /></div>
        <span className="eyebrow">VIRTUAL SHOOT DESK</span>
        <h1>APSAL Studio 0.2.0</h1>
        <p>此界面只在 APSAL Studio Desktop 中运行，用于连接 Codex APSAL 插件。</p>
      </div>
    )
  }

  const gridTemplateColumns = `${leftOpen ? `${leftWidth}px` : '0px'} 8px minmax(540px, 1fr) 8px ${rightOpen ? `${rightWidth}px` : '0px'}`

  return (
    <div className="app-shell">
      <a className="skip-link" href="#protocol-canvas">跳到协议画布</a>
      <header className="app-header">
        <div className="brand">
          <div className="brand-mark"><img src={apsalIcon} alt="" /></div>
          <div className="brand-copy"><strong>APSAL Studio</strong><span><Aperture aria-hidden="true" />Virtual Shoot Desk<i />Stage 01</span></div>
        </div>
        <div className="scene-field" title={snapshot?.project_root}>
          <span>PROJECT · 当前片场</span>
          <strong>{snapshot?.project.project_id ?? '未选择 APSAL 项目'}</strong>
        </div>
        <div className="header-stats">
          <span className={`topbar-stat ${status?.running ? 'online' : ''}`}><ScanSearch aria-hidden="true" />{status?.running ? 'Engine 在线' : 'Engine 启动中'}</span>
          <span className="topbar-stat"><GitBranch aria-hidden="true" />r{snapshot?.revision ?? '—'}</span>
          <span className={`topbar-stat ${linkStatus?.connected ? 'online' : ''}`}>{linkStatus?.connected ? <Link2 aria-hidden="true" /> : <Link2Off aria-hidden="true" />}{linkStatus?.connected ? 'Codex 已连接' : 'Codex 未连接'}</span>
          <span className="version-stat">0.2.0 / 0.15.0</span>
        </div>
        <div className="mode-pill"><GitBranch aria-hidden="true" /><span>工作流 3.1</span></div>
      </header>
      {snapshot?.read_only && <div className="compatibility-banner">只读模式：{snapshot.compatibility_error || '协议版本不兼容，请升级 APSAL Studio 或插件。'}</div>}
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
            zoom={zoom}
            setZoom={setZoom}
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
      {busy && <div className="working-indicator" role="status" aria-live="polite"><RefreshCw aria-hidden="true" />APSAL 正在处理</div>}
      {notice && <div className="notice-toast" role="status" aria-live="polite"><BadgeCheck aria-hidden="true" />{notice}</div>}
      {error && <button type="button" className="error-toast" role="alert" aria-live="assertive" onClick={clearError}>{error}<span>关闭</span></button>}
    </div>
  )
}
