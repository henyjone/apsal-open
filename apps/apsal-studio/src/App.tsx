import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react'
import { LAYERS, nodesToStudioView, projectSnapshot, type ProjectedNode } from './protocol/projection'
import { useStudioStore } from './protocol/store'
import type { ApsalLayerId, ApsalPreview } from './protocol/types'

const WORLD_WIDTH = 1540
const WORLD_HEIGHT = 900

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

function EmptyCanvas({ hasProject, hasSession }: { hasProject: boolean; hasSession: boolean }) {
  return (
    <div className="empty-canvas">
      <div className="empty-mark">A</div>
      <h2>{!hasProject ? '连接一个 APSAL 项目' : !hasSession ? '项目已连接' : '等待协议元素'}</h2>
      <p>
        {!hasProject
          ? '新建或打开项目，然后开启 Codex 联动。'
          : !hasSession
            ? '回到 Codex，用 APSAL 插件开始设计；这里会实时显示同一个项目。'
            : 'Codex 创建元素后，五层节点会出现在画布中。'}
      </p>
    </div>
  )
}

function ProjectPanel() {
  const snapshot = useStudioStore((state) => state.snapshot)
  const status = useStudioStore((state) => state.status)
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const busy = useStudioStore((state) => state.busy)
  const chooseProject = useStudioStore((state) => state.chooseProject)
  const refresh = useStudioStore((state) => state.refresh)
  const setLinkEnabled = useStudioStore((state) => state.setLinkEnabled)

  return (
    <aside className="left-panel">
      <section className="panel-section project-card">
        <div className="section-heading">
          <div>
            <span className="eyebrow">PROJECT</span>
            <h2>APSAL 项目</h2>
          </div>
          <span className={`status-dot ${status?.running ? 'online' : ''}`} title={status?.running ? 'Engine 在线' : 'Engine 未启动'} />
        </div>
        <div className="project-actions">
          <button type="button" disabled={busy} onClick={() => void chooseProject('new')}>新建</button>
          <button type="button" disabled={busy} onClick={() => void chooseProject('open')}>打开</button>
          <button type="button" disabled={busy || !snapshot} onClick={() => void refresh()}>刷新</button>
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

      <section className="panel-section link-card">
        <div className="link-row">
          <div>
            <span className="eyebrow">CODEX LINK</span>
            <h2>Codex 联动</h2>
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
          {linkStatus?.connected ? 'Codex 已连接当前项目' : linkStatus?.enabled ? '联动已开启，等待项目' : '联动默认关闭'}
        </div>
        <p className="muted">开启后，Codex 插件通过本机认证桥更新同一个 `.apsal/` 项目。</p>
      </section>

      <section className="panel-section">
        <span className="eyebrow">FIVE LAYERS</span>
        <div className="layer-list">
          {LAYERS.map((layer, index) => {
            const layerStatus = snapshot?.session?.layers[layer.id]?.status ?? 'pending'
            return (
              <div className={`layer-item ${layerStatus === 'confirmed' ? 'confirmed' : ''}`} key={layer.id}>
                <span className="layer-number">{index + 1}</span>
                <div>
                  <strong>{layer.label}</strong>
                  <span>{layer.short}</span>
                </div>
                <em>{statusLabel(layerStatus)}</em>
              </div>
            )
          })}
        </div>
      </section>

      <section className="panel-section codex-note">
        <span className="eyebrow">WORKFLOW</span>
        <p>创作对话、正式生成和模型视觉 QA 均在 Codex 中进行。Studio 只负责项目可视化、预览确认和布局。</p>
      </section>
    </aside>
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
        <strong>{layerLabel(preview.layer)}</strong>
        <span>{current ? `r${preview.base_revision}` : '已过期'}</span>
      </div>
      <p>{current ? `Codex 提议更新 ${preview.elements.length} 个元素。` : '项目 revision 已变化，需要由 Codex 重新创建预览。'}</p>
      {preview.invalidates_if_applied.length > 0 && current && (
        <div className="impact">影响下游：{preview.invalidates_if_applied.map(layerLabel).join('、')}</div>
      )}
      <div className="preview-actions">
        <button type="button" onClick={() => focusElements(preview.elements.map((item) => item.protocol_element_id))}>定位</button>
        <button type="button" className="accept" disabled={busy || !current || snapshot?.read_only} onClick={() => void confirmPreview(preview)}>确认</button>
        <button type="button" disabled={busy || !current || snapshot?.read_only} onClick={() => void rejectPreview(preview)}>拒绝</button>
      </div>
    </article>
  )
}

function Inspector({ selected }: { selected?: ProjectedNode }) {
  const previews = useStudioStore((state) => state.previews)
  const operations = useStudioStore((state) => state.operations)
  const busy = useStudioStore((state) => state.busy)
  const undoOperation = useStudioStore((state) => state.undoOperation)

  return (
    <aside className="right-panel">
      <section className="inspector-section">
        <div className="inspector-title">
          <span className="eyebrow">PENDING CHANGES</span>
          <em>{previews.length}</em>
        </div>
        {previews.length ? previews.map((preview) => <PreviewCard key={preview.preview_id} preview={preview} />) : <p className="muted">等待 Codex 提交变更预览。</p>}
      </section>

      <section className="inspector-section details">
        <span className="eyebrow">ELEMENT</span>
        {selected ? (
          <>
            <div className="element-title">
              <div>
                <h2>{selected.label}</h2>
                <span>{selected.roleId} · {layerLabel(selected.layerId)}</span>
              </div>
              <em className={selected.ghost ? 'ghost-label' : ''}>{selected.ghost ? '待确认' : statusLabel(selected.status)}</em>
            </div>
            <dl>
              <dt>意图</dt>
              <dd>{selected.intent || '尚未定义'}</dd>
              {selected.attributes.map((attribute) => (
                <div className="attribute" key={attribute.id}>
                  <dt>{attribute.name}</dt>
                  <dd>{attribute.value}</dd>
                </div>
              ))}
            </dl>
            {selected.mustPreserve.length > 0 && <div className="detail-list"><strong>必须保持</strong>{selected.mustPreserve.map((item) => <span key={item}>{item}</span>)}</div>}
            {selected.qaExpectations.length > 0 && <div className="detail-list"><strong>QA</strong>{selected.qaExpectations.map((item) => <span key={item}>{item}</span>)}</div>}
            <p className="readonly-note">语义由 APSAL Engine 管理；编辑请在 Codex 中提出。</p>
          </>
        ) : (
          <p className="muted">选择画布节点查看只读语义。</p>
        )}
      </section>

      {operations.length > 0 && (
        <section className="inspector-section">
          <span className="eyebrow">RECENT OPERATIONS</span>
          <div className="operation-list">
            {operations.map((operation) => (
              <div className="operation" key={operation.operationId}>
                <div><strong>{METHOD_LABELS[operation.method] ?? operation.method}</strong><span>r{operation.revision ?? '?'}</span></div>
                {operation.undoable && !['project.undo', 'design.propose'].includes(operation.method) && (
                  <button type="button" disabled={busy} onClick={() => void undoOperation(operation.operationId)}>撤销</button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </aside>
  )
}

function ProtocolCanvas({ nodes, setNodes, zoom, setZoom }: {
  nodes: ProjectedNode[]
  setNodes: (nodes: ProjectedNode[]) => void
  zoom: number
  setZoom: (zoom: number) => void
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
    if (node.ghost || snapshot?.read_only) return
    drag.current = { id: node.id, startX: event.clientX, startY: event.clientY, originX: node.x, originY: node.y }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  const moveDrag = (event: ReactPointerEvent) => {
    if (!drag.current) return
    const current = drag.current
    const next = nodes.map((node) => node.id === current.id ? {
      ...node,
      x: current.originX + (event.clientX - current.startX) / zoom,
      y: current.originY + (event.clientY - current.startY) / zoom,
    } : node)
    setNodes(next)
  }

  const endDrag = (event: ReactPointerEvent) => {
    if (!drag.current) return
    drag.current = null
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
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
    <main className="canvas-shell" id="protocol-canvas" tabIndex={-1}>
      <div className="canvas-toolbar">
        <div><span className="eyebrow">PROTOCOL CANVAS</span><strong>{snapshot?.theme?.name ?? snapshot?.session?.brief ?? 'APSAL Studio'}</strong></div>
        <div className="zoom-controls">
          <button type="button" onClick={() => changeZoom(zoom - 0.1)}>−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button type="button" onClick={() => changeZoom(zoom + 0.1)}>＋</button>
        </div>
      </div>
      <div className="canvas-scroll" onPointerMove={moveDrag} onPointerUp={endDrag} onPointerCancel={endDrag}>
        {!nodes.length ? (
          <EmptyCanvas hasProject={Boolean(snapshot)} hasSession={Boolean(snapshot?.session)} />
        ) : (
          <div className="world-scale" style={{ width: WORLD_WIDTH * zoom, height: WORLD_HEIGHT * zoom }}>
            <div className="world" style={{ width: WORLD_WIDTH, height: WORLD_HEIGHT, transform: `scale(${zoom})` }}>
              {LAYERS.map((layer, index) => (
                <div className="layer-column" key={layer.id} style={{ left: 24 + index * 300 }}>
                  <span>{String(index + 1).padStart(2, '0')}</span>
                  <strong>{layer.label}</strong>
                  <em>{layer.short}</em>
                </div>
              ))}
              {nodes.map((node) => {
                const selected = selectedElementId === node.protocolElementId
                const focused = focusElementIds.includes(node.protocolElementId)
                return (
                  <div
                    className={`protocol-node ${node.ghost ? 'ghost' : ''} ${selected ? 'selected' : ''} ${focused ? 'focused' : ''}`}
                    key={node.id}
                    style={{ left: node.x, top: node.y }}
                    role="button"
                    tabIndex={0}
                    aria-label={`${node.label}，${node.ghost ? '待确认预览' : statusLabel(node.status)}`}
                    onPointerDown={(event) => beginDrag(event, node)}
                    onClick={() => selectElement(node.protocolElementId)}
                    onKeyDown={(event) => {
                      if (moveNodeWithKeyboard(event, node)) return
                      if (event.key === 'Enter' || event.key === ' ') selectElement(node.protocolElementId)
                    }}
                  >
                    <div className="node-topline"><span>{node.roleId}</span><em>{node.ghost ? 'PREVIEW' : statusLabel(node.status)}</em></div>
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
    </main>
  )
}

export function App() {
  const available = useStudioStore((state) => state.available)
  const initialize = useStudioStore((state) => state.initialize)
  const snapshot = useStudioStore((state) => state.snapshot)
  const view = useStudioStore((state) => state.view)
  const previews = useStudioStore((state) => state.previews)
  const selectedElementId = useStudioStore((state) => state.selectedElementId)
  const error = useStudioStore((state) => state.error)
  const busy = useStudioStore((state) => state.busy)
  const clearError = useStudioStore((state) => state.clearError)
  const linkStatus = useStudioStore((state) => state.linkStatus)
  const [nodes, setNodes] = useState<ProjectedNode[]>([])
  const [zoom, setZoom] = useState(0.82)

  useEffect(() => { void initialize() }, [initialize])
  useEffect(() => {
    setNodes(snapshot ? projectSnapshot(snapshot, view, previews) : [])
    setZoom(Number(view?.viewport?.zoom ?? 0.82))
  }, [snapshot, view, previews])

  const selected = useMemo(
    () => nodes.find((node) => node.protocolElementId === selectedElementId && !node.ghost)
      ?? nodes.find((node) => node.protocolElementId === selectedElementId),
    [nodes, selectedElementId],
  )

  if (!available) {
    return (
      <div className="desktop-required">
        <div className="brand-mark">A</div>
        <h1>APSAL Studio 0.2.0</h1>
        <p>此界面只在 APSAL Studio Desktop 中运行，用于连接 Codex APSAL 插件。</p>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#protocol-canvas">跳到协议画布</a>
      <header className="app-header">
        <div className="brand"><div className="brand-mark">A</div><div><strong>APSAL Studio</strong><span>Codex Plugin Frontend</span></div></div>
        <div className="header-meta">
          <span>Studio 0.2.0</span>
          <span>Protocol 0.15.0</span>
          {busy && <span className="working" aria-live="polite">WORKING</span>}
          <span className={linkStatus?.connected ? 'live' : ''}>{linkStatus?.connected ? 'LIVE' : 'OFFLINE'}</span>
        </div>
      </header>
      {snapshot?.read_only && <div className="compatibility-banner">只读模式：{snapshot.compatibility_error || '协议版本不兼容，请升级 APSAL Studio 或插件。'}</div>}
      <div className="workspace">
        <ProjectPanel />
        <ProtocolCanvas nodes={nodes} setNodes={setNodes} zoom={zoom} setZoom={setZoom} />
        <Inspector selected={selected} />
      </div>
      {error && <button type="button" className="error-toast" role="alert" aria-live="assertive" onClick={clearError}>{error}<span>关闭</span></button>}
    </div>
  )
}
