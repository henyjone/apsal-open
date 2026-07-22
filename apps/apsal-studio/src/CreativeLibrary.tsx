import {
  Archive,
  ArrowRight,
  BadgeCheck,
  Boxes,
  GitBranch,
  Heart,
  ImagePlus,
  Images,
  LoaderCircle,
  PackageOpen,
  RefreshCw,
  Search,
  Share2,
  Sparkles,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ApsalProjectSnapshot } from './protocol/types'

type ProjectKind = 'root' | 'fork' | 'imported'

interface LibraryProject {
  project_id: string
  project_root: string
  name: string
  project_kind: ProjectKind
  parent_project_id?: string | null
  origin_project_id?: string | null
  stage: string
  reference_count: number
  output_count: number
  cover_path?: string | null
  tags: string[]
  favorite: boolean
  archived: boolean
  updated_at: string
}

interface LibraryAsset {
  asset_id: string
  kind: 'reference' | 'output'
  archived_path?: string
  path?: string
  role?: string
  shot_id?: string
  qa_status?: string
}

interface LibraryAnalysis {
  analysis_id: string
  status: string
  job_count: number
  completed_job_count: number
  design_session_id?: string
}

interface LibraryShare {
  share_id: string
  platform: 'x' | 'xiaohongshu'
  status: string
  publication?: { url?: string; published?: boolean }
}

interface LibraryDetail {
  project: LibraryProject
  assets: LibraryAsset[]
  analyses: LibraryAnalysis[]
  shares: LibraryShare[]
  lineage?: {
    ancestors: LibraryProject[]
    children: LibraryProject[]
    comparison: { inherited: string[]; modified: string[]; added: string[]; removed: string[]; available: boolean }
  }
}

interface ReferenceDraft {
  path: string
  role: 'subject' | 'space' | 'composition' | 'lighting' | 'wardrobe' | 'color' | 'style'
  identity: boolean
}

interface SharePreview {
  project: LibraryProject
  platform: 'x' | 'xiaohongshu'
  shareId: string
  revision: number
  content: {
    title: string
    text: string
    hashtags: string[]
    images: Array<{ path: string }>
    project_url: string
  }
}

const STAGE_LABELS: Record<string, string> = {
  references_ready: '参考图已入库',
  analyzing: 'Codex 分析中',
  design_ready: '分析已完成',
  skill_ready: 'Prompt / Skill 就绪',
  generating: '扩展生成中',
  review_ready: '等待视觉 QA',
  published: '已公开发布',
}

const ROLE_LABELS: Record<ReferenceDraft['role'], string> = {
  subject: '人物 / 主体',
  space: '空间',
  composition: '构图',
  lighting: '灯光',
  wardrobe: '服装造型',
  color: '色彩',
  style: '风格',
}

const ROLE_USES: Record<ReferenceDraft['role'], string[]> = {
  subject: ['subject'],
  space: ['space', 'world'],
  composition: ['composition'],
  lighting: ['lighting'],
  wardrobe: ['wardrobe'],
  color: ['color'],
  style: ['style'],
}

const APSAL_ROLE_LABELS: Record<string, string> = {
  content: '创作命题', emotion: '情绪', subject: '人物', world: '世界', look: '妆造',
  event: '事件', sequence: '序列', camera: '相机', light: '灯光', style: '风格',
  color_post: '色彩与后期', job: '生成任务', quality_control: '质量检查',
}

const PIPELINE = [
  ['references_ready', '参考图'],
  ['analyzing', '分析'],
  ['design_ready', '设计'],
  ['skill_ready', 'Skill'],
  ['generating', '生成'],
  ['review_ready', 'QA'],
  ['published', '分享'],
] as const

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function mediaUrl(path?: string | null): string | undefined {
  return path ? `apsal-media://asset?path=${encodeURIComponent(path)}` : undefined
}

function operationId(prefix: string): string {
  return `STUDIO-${prefix}-${crypto.randomUUID()}`
}

function stageIndex(stage: string): number {
  const index = PIPELINE.findIndex(([value]) => value === stage)
  return index < 0 ? 0 : index
}

function ProjectPipeline({ stage }: { stage: string }) {
  const current = stageIndex(stage)
  return (
    <ol className="library-pipeline" aria-label="APSAL 项目流水线">
      {PIPELINE.map(([value, label], index) => (
        <li key={value} className={index < current ? 'complete' : index === current ? 'current' : ''}>
          <i aria-hidden="true">{index + 1}</i><span>{label}</span>
        </li>
      ))}
    </ol>
  )
}

function ProjectCard({ project, selected, onSelect }: {
  project: LibraryProject
  selected: boolean
  onSelect: () => void
}) {
  const cover = mediaUrl(project.cover_path)
  return (
    <button type="button" className={`library-card ${selected ? 'selected' : ''}`} onClick={onSelect}>
      <span className="library-cover">
        {cover ? <img src={cover} alt={`${project.name} 项目封面`} loading="lazy" /> : <Images aria-hidden="true" />}
        <span className="library-kind">{project.project_kind === 'fork' ? '分叉' : project.project_kind === 'imported' ? '导入' : '根项目'}</span>
        {project.favorite && <Heart className="library-favorite" aria-label="已收藏" />}
      </span>
      <span className="library-card-copy">
        <span className="library-card-stage">{STAGE_LABELS[project.stage] ?? project.stage}</span>
        <strong>{project.name}</strong>
        <span className="library-card-counts"><span>{project.reference_count} 张参考</span><i /> <span>{project.output_count} 张产出</span></span>
        {project.parent_project_id && <span className="library-parent"><GitBranch aria-hidden="true" />来自 {project.parent_project_id}</span>}
      </span>
    </button>
  )
}

function CreateProjectSheet({ onClose, onCreated }: {
  onClose: () => void
  onCreated: (snapshot: ApsalProjectSnapshot) => void
}) {
  const runtime = window.apsalProtocol
  const [name, setName] = useState('')
  const [references, setReferences] = useState<ReferenceDraft[]>([])
  const [copyrightStatus, setCopyrightStatus] = useState('owned')
  const [portraitRights, setPortraitRights] = useState('not_applicable')
  const [attribution, setAttribution] = useState('本人拥有或已获许可')
  const [aiAllowed, setAiAllowed] = useState(false)
  const [redistribution, setRedistribution] = useState(false)
  const [identityAuthorized, setIdentityAuthorized] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const choose = async () => {
    if (!runtime) return
    const paths = await runtime.chooseReferences()
    setReferences((current) => {
      const existing = new Set(current.map((item) => item.path))
      return [...current, ...paths.filter((path) => !existing.has(path)).map((path) => ({ path, role: 'style' as const, identity: false }))].slice(0, 24)
    })
  }

  const submit = async () => {
    if (!runtime) return
    if (!name.trim() || references.length === 0 || !attribution.trim()) {
      setError('请填写项目名称、权利归属，并至少选择一张参考图。')
      return
    }
    if (!aiAllowed) {
      setError('“允许 AI 分析与改编”未确认；可以取消创建，或明确勾选后继续。')
      return
    }
    if (references.some((item) => item.identity) && (!identityAuthorized || !['owned', 'licensed', 'confirmed'].includes(portraitRights))) {
      setError('使用真人身份连续性时，必须单独确认肖像与身份使用授权。')
      return
    }
    setBusy(true)
    setError('')
    try {
      const rights = {
        copyright_status: copyrightStatus,
        portrait_rights: portraitRights,
        redistribution_allowed: redistribution,
        ai_modification_allowed: aiAllowed,
        identity_use_allowed: identityAuthorized,
        attribution: attribution.trim(),
      }
      const result = await runtime.createReferenceProject({
        name: name.trim(),
        references: references.map((item) => ({
          path: item.path,
          role: item.role,
          uses: [...ROLE_USES[item.role], ...(item.identity ? ['identity'] : [])],
          rights,
        })),
      })
      onCreated(result.snapshot)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="library-sheet-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="library-sheet" role="dialog" aria-modal="true" aria-labelledby="create-project-title">
        <header><div><span className="eyebrow">新建参考图项目</span><h2 id="create-project-title">一次上传，建立一个可追溯根项目</h2></div><button type="button" className="sheet-close" onClick={onClose} aria-label="关闭"><X /></button></header>
        <div className="library-sheet-body">
          <label className="field-label" htmlFor="project-name">项目名称 *</label>
          <input id="project-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：雨夜窗边叙事人像" autoFocus />
          <div className="reference-picker-head"><div><strong>参考图片 *</strong><span>每张图都要声明角色；原图进入私有内容寻址保险库。</span></div><button type="button" className="button-ghost" onClick={() => void choose()}><ImagePlus />选择图片</button></div>
          {references.length === 0 ? <button type="button" className="reference-empty" onClick={() => void choose()}><Images /><strong>选择 1–24 张参考图片</strong><span>支持 PNG、JPEG、WebP</span></button> : (
            <div className="reference-draft-grid">
              {references.map((item, index) => (
                <article key={item.path} className="reference-draft">
                  <img src={mediaUrl(item.path)} alt={`参考图 ${index + 1}`} />
                  <div><label htmlFor={`role-${index}`}>参考角色</label><select id={`role-${index}`} value={item.role} onChange={(event) => setReferences((current) => current.map((value, position) => position === index ? { ...value, role: event.target.value as ReferenceDraft['role'], identity: event.target.value === 'subject' ? value.identity : false } : value))}>{Object.entries(ROLE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
                  {item.role === 'subject' && <label className="compact-check"><input type="checkbox" checked={item.identity} onChange={(event) => setReferences((current) => current.map((value, position) => position === index ? { ...value, identity: event.target.checked } : value))} />保持真人身份连续性</label>}
                  <button type="button" className="reference-remove" onClick={() => setReferences((current) => current.filter((_, position) => position !== index))} aria-label={`移除参考图 ${index + 1}`}><X /></button>
                </article>
              ))}
            </div>
          )}
          <fieldset className="rights-fieldset">
            <legend>权利与公开边界 *</legend>
            <p>这些选择会逐张写入项目。未确认的项目可以归档，但不能自动分析、构建公开包或发布社媒。</p>
            <div className="rights-grid">
              <label><span>著作权状态</span><select value={copyrightStatus} onChange={(event) => setCopyrightStatus(event.target.value)}><option value="owned">本人拥有</option><option value="licensed">已获许可</option><option value="public_domain">公共领域</option><option value="user_provided_unverified">尚待确认</option></select></label>
              <label><span>肖像授权</span><select value={portraitRights} onChange={(event) => setPortraitRights(event.target.value)}><option value="not_applicable">不涉及真人肖像</option><option value="owned">本人肖像</option><option value="licensed">已获许可</option><option value="confirmed">已明确确认</option><option value="pending">尚待确认</option></select></label>
              <label className="rights-attribution"><span>权利归属 / 署名</span><input value={attribution} onChange={(event) => setAttribution(event.target.value)} /></label>
            </div>
            <div className="rights-checks">
              <label><input type="checkbox" checked={aiAllowed} onChange={(event) => setAiAllowed(event.target.checked)} />允许 AI 分析与改编</label>
              <label><input type="checkbox" checked={redistribution} onChange={(event) => setRedistribution(event.target.checked)} />允许原参考图再分发</label>
              <label><input type="checkbox" checked={identityAuthorized} onChange={(event) => setIdentityAuthorized(event.target.checked)} />单独授权真人身份保持</label>
            </div>
          </fieldset>
          {error && <div className="sheet-error" role="alert">{error}</div>}
        </div>
        <footer><span>默认保存到 ~/APSAL Projects/，项目目录是语义真源。</span><div><button type="button" className="button-ghost" onClick={onClose}>取消</button><button type="button" className="button-primary" disabled={busy} onClick={() => void submit()}>{busy ? <LoaderCircle className="spin" /> : <Sparkles />}创建根项目</button></div></footer>
      </section>
    </div>
  )
}

const FORK_TYPES = [
  ['series_extension', '同系列延伸'],
  ['scene_variation', '场景变化'],
  ['camera_variation', '镜头变化'],
  ['lighting_variation', '灯光变化'],
  ['styling_variation', '造型变化'],
  ['nine_shot_theme', '完整九图主题'],
] as const

function ForkProjectSheet({ project, assets, onClose, onCreated }: {
  project: LibraryProject
  assets: LibraryAsset[]
  onClose: () => void
  onCreated: () => void
}) {
  const runtime = window.apsalProtocol
  const [name, setName] = useState(`${project.name} · 系列延伸`)
  const [forkType, setForkType] = useState<(typeof FORK_TYPES)[number][0]>('series_extension')
  const [sourceAssetIds, setSourceAssetIds] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const toggleAsset = (assetId: string) => {
    setSourceAssetIds((current) => current.includes(assetId)
      ? current.filter((value) => value !== assetId)
      : [...current, assetId])
  }

  const submit = async () => {
    if (!runtime || !name.trim()) {
      setError('请输入扩展子项目名称。')
      return
    }
    setBusy(true)
    setError('')
    try {
      await runtime.createForkProject({
        parent_project_root: project.project_root,
        name: name.trim(),
        fork_type: forkType,
        source_asset_ids: sourceAssetIds,
      })
      onCreated()
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="library-sheet-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="fork-project-sheet" role="dialog" aria-modal="true" aria-labelledby="fork-project-title">
        <header><div><span className="eyebrow">创建扩展子项目</span><h2 id="fork-project-title">保留父项目，沿一个方向继续创作</h2></div><button type="button" className="sheet-close" onClick={onClose} aria-label="关闭"><X /></button></header>
        <div className="library-sheet-body">
          <div className="fork-parent"><GitBranch /><div><span>不可变父项目</span><strong>{project.name}</strong><code>{project.project_id}</code></div></div>
          <label className="field-label" htmlFor="fork-project-name">子项目名称 *</label>
          <input id="fork-project-name" value={name} onChange={(event) => setName(event.target.value)} autoFocus />
          <label className="field-label" htmlFor="fork-type">扩展方向 *</label>
          <select id="fork-type" value={forkType} onChange={(event) => setForkType(event.target.value as typeof forkType)}>{FORK_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>
          <div className="fork-assets-head"><strong>绑定来源图片</strong><span>可不选，表示继承整组获准使用的视觉 DNA；选择后会写入谱系。</span></div>
          {assets.length > 0 ? <div className="fork-assets">{assets.slice(0, 24).map((asset) => {
            const source = mediaUrl(asset.archived_path || asset.path)
            const checked = sourceAssetIds.includes(asset.asset_id)
            return <label key={asset.asset_id} className={checked ? 'selected' : ''}><input type="checkbox" checked={checked} onChange={() => toggleAsset(asset.asset_id)} />{source ? <img src={source} alt={asset.kind === 'reference' ? '参考图片' : `生成结果 ${asset.shot_id || ''}`} /> : <Images />}<span>{asset.kind === 'reference' ? '参考' : asset.shot_id || '产出'}</span></label>
          })}</div> : <div className="fork-assets-empty">当前没有可单独绑定的图片，将继承项目级视觉 DNA。</div>}
          <p className="fork-note">创建后会记录父快照摘要、来源图片和变化方向；父项目的文件与版本号保持不变。</p>
          {error && <div className="sheet-error" role="alert">{error}</div>}
        </div>
        <footer><button type="button" className="button-ghost" onClick={onClose}>取消</button><button type="button" className="button-primary" disabled={busy} onClick={() => void submit()}>{busy ? <LoaderCircle className="spin" /> : <GitBranch />}创建扩展子项目</button></footer>
      </section>
    </div>
  )
}

function SharePreviewSheet({ preview, onClose, onComplete }: {
  preview: SharePreview
  onClose: () => void
  onComplete: (message: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const publish = async () => {
    const runtime = window.apsalProtocol
    if (!runtime) return
    setBusy(true)
    setError('')
    try {
      await runtime.openProject(preview.project.project_root)
      const confirmed = await runtime.call<{ confirmation_token: string; revision: number }>('share.confirm', {
        share_id: preview.shareId,
        confirmed_public: true,
        expected_revision: preview.revision,
        operation_id: operationId('SHARE-CONFIRM'),
      })
      const result = await runtime.call<{ status: string; publication?: { url?: string; published?: boolean; copy_text?: string; export_directory?: string } }>('share.publish', {
        share_id: preview.shareId,
        confirmation_token: confirmed.confirmation_token,
        expected_revision: confirmed.revision,
        operation_id: operationId('SHARE-PUBLISH'),
      })
      if (result.publication?.url && result.status === 'awaiting_external_confirmation') {
        if (result.publication.copy_text && navigator.clipboard?.writeText) {
          try {
            await navigator.clipboard.writeText(result.publication.copy_text)
          } catch {
            // Exported images and the visible preview remain available if the OS denies clipboard access.
          }
        }
        await runtime.openExternal(result.publication.url)
      }
      onComplete(result.status === 'published' ? '已通过官方接口发布。' : `文案已复制、图片已导出${result.publication?.export_directory ? `到 ${result.publication.export_directory}` : ''}，并打开官方发布流程；完成前不会标记为已发布。`)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="library-sheet-backdrop" role="presentation">
      <section className="share-preview-sheet" role="dialog" aria-modal="true" aria-labelledby="share-preview-title">
        <header><div><span className="eyebrow">最终发布预览 · {preview.platform === 'x' ? 'X' : '小红书'}</span><h2 id="share-preview-title">{preview.content.title}</h2></div><button type="button" className="sheet-close" onClick={onClose} aria-label="关闭"><X /></button></header>
        <div className="share-preview-body"><p>{preview.content.text}</p><div className="share-tags">{preview.content.hashtags.map((tag) => <span key={tag}>#{tag.replace(/^#/, '')}</span>)}</div><div className="share-facts"><span>{preview.content.images.length} 张生成图片</span><span>AI 媒体标记：是</span><span>项目链接：{preview.content.project_url}</span></div><div className="share-warning">确认令牌仅绑定此版本的图片、文案、平台和权限。任何内容变化都会使令牌失效。</div>{error && <div className="sheet-error" role="alert">{error}</div>}</div>
        <footer><button type="button" className="button-ghost" onClick={onClose}>返回修改</button><button type="button" className="button-primary" disabled={busy} onClick={() => void publish()}>{busy ? <LoaderCircle className="spin" /> : <Share2 />}确认并进入官方发布</button></footer>
      </section>
    </div>
  )
}

export function CreativeLibrary({ onOpenProject }: { onOpenProject: () => void }) {
  const runtime = window.apsalProtocol
  const [projects, setProjects] = useState<LibraryProject[]>([])
  const [query, setQuery] = useState('')
  const [archived, setArchived] = useState(false)
  const [favoriteOnly, setFavoriteOnly] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<LibraryDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyAction, setBusyAction] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [creating, setCreating] = useState(false)
  const [creatingFork, setCreatingFork] = useState(false)
  const [sharePreview, setSharePreview] = useState<SharePreview | null>(null)
  const [tagInput, setTagInput] = useState('')

  const load = useCallback(async () => {
    if (!runtime) return
    setLoading(true)
    setError('')
    try {
      const result = await runtime.call<{ projects: LibraryProject[] }>('library.list', {
        query: query.trim(), archived, favorite: favoriteOnly ? true : undefined, limit: 100,
      })
      setProjects(result.projects)
      if (selectedId && !result.projects.some((project) => project.project_id === selectedId)) {
        setSelectedId(null)
        setDetail(null)
      }
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [archived, favoriteOnly, query, runtime, selectedId])

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 180)
    return () => window.clearTimeout(timer)
  }, [load])
  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 4200)
    return () => window.clearTimeout(timer)
  }, [notice])

  const selectProjectById = async (projectId: string) => {
    if (!runtime) return
    setSelectedId(projectId)
    setBusyAction('detail')
    try {
      const [value, lineage] = await Promise.all([
        runtime.call<LibraryDetail>('library.get', { project_id: projectId }),
        runtime.call<NonNullable<LibraryDetail['lineage']>>('library.lineage', { project_id: projectId }),
      ])
      setDetail({ ...value, lineage })
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const selectProject = async (project: LibraryProject) => selectProjectById(project.project_id)

  const handleProjectCreated = async (snapshot: ApsalProjectSnapshot) => {
    setCreating(false)
    setNotice('参考图已安全入库并显示在项目详情中；下一步可启动 Codex 分析。')
    await load()
    await selectProjectById(snapshot.project.project_id)
  }

  const openProject = async (project: LibraryProject, switchView = true): Promise<ApsalProjectSnapshot | null> => {
    if (!runtime) return null
    const snapshot = await runtime.openProject(project.project_root)
    if (switchView) onOpenProject()
    return snapshot
  }

  const startAnalysis = async () => {
    if (!detail || !runtime) return
    setBusyAction('analysis')
    try {
      const snapshot = await openProject(detail.project, false)
      if (!snapshot) return
      const result = await runtime.call<{ analysis_id: string }>('analysis.start', {
        expected_revision: snapshot.revision,
        operation_id: operationId('ANALYSIS-START'),
      })
      setNotice(`分析任务 ${result.analysis_id} 已建立；Codex 可逐张领取并回写结构化结果。`)
      await runtime.call('library.reconcile')
      await selectProject(detail.project)
      await load()
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const buildDesign = async () => {
    if (!detail || !runtime) return
    const analysis = [...detail.analyses].reverse().find((item) => item.status === 'completed' && !item.design_session_id)
    if (!analysis) return
    setBusyAction('build')
    try {
      const snapshot = await openProject(detail.project, false)
      if (!snapshot) return
      await runtime.call('design.build_from_analysis', {
        analysis_id: analysis.analysis_id,
        expected_revision: snapshot.revision,
        operation_id: operationId('BUILD'),
      })
      setNotice('APSAL 主题、Prompt、QA 与 Skill 已自动构建。')
      await selectProject(detail.project)
      await load()
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const exportPublic = async () => {
    if (!detail || !runtime) return
    if (!window.confirm('公开包默认不含原始参考图和本地路径。确认按当前权限生成可分享项目包？')) return
    setBusyAction('export')
    try {
      await openProject(detail.project, false)
      const result = await runtime.call<{ path: string }>('project.export', { distribution: 'public', confirmed_public: true })
      setNotice(`公开分享包已生成：${result.path}`)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const draftShare = async (platform: 'x' | 'xiaohongshu') => {
    if (!detail || !runtime) return
    setBusyAction(`share-${platform}`)
    try {
      const snapshot = await openProject(detail.project, false)
      if (!snapshot) return
      const draft = await runtime.call<{ share_id: string; revision: number; content: SharePreview['content'] }>('share.draft', {
        platform,
        expected_revision: snapshot.revision,
        operation_id: operationId('SHARE-DRAFT'),
      })
      const preview = await runtime.call<{ content: SharePreview['content'] }>('share.preview', { share_id: draft.share_id })
      setSharePreview({ project: detail.project, platform, shareId: draft.share_id, revision: draft.revision, content: preview.content })
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const toggleFavorite = async () => {
    if (!detail || !runtime) return
    await runtime.call('library.update', { project_id: detail.project.project_id, favorite: !detail.project.favorite })
    await load()
    await selectProject({ ...detail.project, favorite: !detail.project.favorite })
  }

  const archiveProject = async () => {
    if (!detail || !runtime) return
    if (!window.confirm(detail.project.archived ? '确认把项目恢复到项目库？' : '只归档索引，不删除项目目录。确认归档？')) return
    await runtime.call('library.archive', { project_id: detail.project.project_id, archived: !detail.project.archived })
    setDetail(null)
    setSelectedId(null)
    await load()
  }

  const updateTags = async (tags: string[]) => {
    if (!detail || !runtime) return
    const cleaned = [...new Set(tags.map((value) => value.trim()).filter(Boolean))].slice(0, 30)
    try {
      const project = await runtime.call<LibraryProject>('library.update', {
        project_id: detail.project.project_id,
        tags: cleaned,
      })
      setDetail({ ...detail, project })
      setTagInput('')
      await load()
    } catch (error) {
      setError(errorMessage(error))
    }
  }

  const importPackage = async () => {
    if (!runtime) return
    setBusyAction('import')
    setError('')
    try {
      const result = await runtime.importProjectPackage()
      if (result) {
        setNotice('分享包已作为新的本地项目导入，并保留来源项目 ID 与包摘要。')
        await load()
      }
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setBusyAction('')
    }
  }

  const referenceAssets = useMemo(() => detail?.assets.filter((item) => item.kind === 'reference') ?? [], [detail])
  const outputAssets = useMemo(() => detail?.assets.filter((item) => item.kind === 'output') ?? [], [detail])
  const latestAnalysis = detail?.analyses.at(-1)

  return (
    <main className="creative-library" id="creative-library" tabIndex={-1}>
      <section className="library-hero">
        <div><span className="eyebrow">APSAL 创作项目库</span><h1>从参考图，到可分享的摄影创作系统</h1><p>每一次多图导入建立根项目；每一次扩展都创建有谱系的子项目。项目目录保留语义真源，项目库只负责查找、封面和展示。</p></div>
        <div className="library-hero-actions"><button type="button" className="button-ghost" disabled={Boolean(busyAction)} onClick={() => void importPackage()}>{busyAction === 'import' ? <LoaderCircle className="spin" /> : <PackageOpen />}导入项目包</button><button type="button" className="button-primary library-create" onClick={() => setCreating(true)}><ImagePlus />新建参考图项目</button></div>
      </section>
      <section className="library-toolbar" aria-label="项目库筛选">
        <label className="library-search"><Search aria-hidden="true" /><span className="sr-only">搜索项目</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索项目、标签或视觉 DNA" /></label>
        <div className="library-filters"><button type="button" className={favoriteOnly ? 'active' : ''} onClick={() => setFavoriteOnly((value) => !value)}><Heart />收藏</button><button type="button" className={archived ? 'active' : ''} onClick={() => setArchived((value) => !value)}><Archive />{archived ? '归档项目' : '当前项目'}</button><button type="button" onClick={() => void load()} aria-label="刷新项目库"><RefreshCw /></button></div>
      </section>
      {error && <button type="button" className="library-error" onClick={() => setError('')} role="alert">{error}<span>关闭</span></button>}
      {notice && <div className="library-notice" role="status"><BadgeCheck />{notice}</div>}
      <div className={`library-content ${detail ? 'has-detail' : ''}`}>
        <section className="library-grid" aria-busy={loading}>
          {loading && projects.length === 0 ? Array.from({ length: 6 }, (_, index) => <div key={index} className="library-card skeleton" />) : projects.map((project) => <ProjectCard key={project.project_id} project={project} selected={selectedId === project.project_id} onSelect={() => void selectProject(project)} />)}
          {!loading && projects.length === 0 && <div className="library-empty"><Boxes /><h2>{query ? '没有匹配的项目' : archived ? '归档区是空的' : '建立第一个 APSAL 创作项目'}</h2><p>选择多张参考图片，记录权利边界，再让 Codex 按五层十三要素开始分析。</p><button type="button" className="button-primary" onClick={() => setCreating(true)}><ImagePlus />新建参考图项目</button></div>}
        </section>
        {detail && <aside className="library-detail" aria-label="项目详情">
          <header><div><span className="eyebrow">{detail.project.project_kind === 'fork' ? '分叉项目' : detail.project.project_kind === 'imported' ? '导入项目' : '根项目'}</span><h2>{detail.project.name}</h2><code>{detail.project.project_id}</code></div><button type="button" className="sheet-close" onClick={() => { setDetail(null); setSelectedId(null) }} aria-label="关闭详情"><X /></button></header>
          <ProjectPipeline stage={detail.project.stage} />
          <div className="detail-summary"><span><strong>{detail.project.reference_count}</strong>参考图</span><span><strong>{detail.project.output_count}</strong>产出</span><span><strong>{detail.analyses.length}</strong>分析批次</span></div>
          {detail.project.parent_project_id && <div className="lineage-callout"><GitBranch /><div><strong>继承自父项目</strong><span>{detail.project.parent_project_id}</span></div></div>}
          {detail.lineage?.comparison.available && <section className="lineage-comparison"><h3>五层十三要素谱系比较</h3><div><span><strong>{detail.lineage.comparison.inherited.length}</strong>继承</span><span><strong>{detail.lineage.comparison.modified.length}</strong>修改</span><span><strong>{detail.lineage.comparison.added.length}</strong>新增</span></div>{detail.lineage.comparison.modified.length > 0 && <p>修改：{detail.lineage.comparison.modified.map((role) => APSAL_ROLE_LABELS[role] || role).join('、')}</p>}{detail.lineage.comparison.added.length > 0 && <p>新增：{detail.lineage.comparison.added.map((role) => APSAL_ROLE_LABELS[role] || role).join('、')}</p>}</section>}
          {referenceAssets.length > 0 && <section className="detail-media"><h3>参考图片</h3><div className="detail-gallery">{referenceAssets.slice(0, 12).map((item, index) => <img key={item.asset_id} src={mediaUrl(item.archived_path || item.path)} alt={`参考图片 ${index + 1}`} loading="lazy" />)}</div></section>}
          {outputAssets.length > 0 && <section className="detail-media"><h3>生成结果</h3><div className="detail-gallery">{outputAssets.slice(0, 6).map((item) => <img key={item.asset_id} src={mediaUrl(item.archived_path || item.path)} alt={`生成结果 ${item.shot_id || ''}`} loading="lazy" />)}</div></section>}
          {latestAnalysis && <div className="analysis-progress"><Sparkles /><div><strong>{latestAnalysis.status === 'completed' ? 'Codex 分析已完成' : '等待 Codex 分析'}</strong><span>{latestAnalysis.completed_job_count} / {latestAnalysis.job_count} 个结构化任务已回写</span></div></div>}
          <div className="detail-actions">
            <button type="button" className="button-primary" onClick={() => void openProject(detail.project)}><ArrowRight />进入工作流画布</button>
            <button type="button" className="button-ghost" disabled={Boolean(busyAction)} onClick={() => setCreatingFork(true)}><GitBranch />创建扩展子项目</button>
            {detail.analyses.length === 0 && <button type="button" className="button-ghost" disabled={Boolean(busyAction)} onClick={() => void startAnalysis()}>{busyAction === 'analysis' ? <LoaderCircle className="spin" /> : <Sparkles />}开始 Codex 分析</button>}
            {detail.analyses.some((item) => item.status === 'completed' && !item.design_session_id) && <button type="button" className="button-ghost" disabled={Boolean(busyAction)} onClick={() => void buildDesign()}>{busyAction === 'build' ? <LoaderCircle className="spin" /> : <PackageOpen />}全自动构建 Prompt / Skill</button>}
            <button type="button" className="button-ghost" disabled={Boolean(busyAction)} onClick={() => void exportPublic()}><PackageOpen />导出公开项目包</button>
          </div>
          <section className="library-tags"><h3>项目标签</h3><div>{detail.project.tags.map((tag) => <button key={tag} type="button" title="移除标签" onClick={() => void updateTags(detail.project.tags.filter((value) => value !== tag))}>#{tag}<X /></button>)}</div><form onSubmit={(event) => { event.preventDefault(); if (tagInput.trim()) void updateTags([...detail.project.tags, tagInput]) }}><input value={tagInput} maxLength={40} onChange={(event) => setTagInput(event.target.value)} placeholder="添加标签" aria-label="添加项目标签" /><button type="submit" disabled={!tagInput.trim()}>添加</button></form></section>
          <section className="share-actions"><h3>传播草稿</h3><p>逐平台显示最终预览并确认；未确认不发布。</p><div><button type="button" disabled={detail.project.output_count === 0 || Boolean(busyAction)} onClick={() => void draftShare('x')}><Share2 />X 草稿</button><button type="button" disabled={detail.project.output_count === 0 || Boolean(busyAction)} onClick={() => void draftShare('xiaohongshu')}><Share2 />小红书草稿</button></div>{detail.shares.map((share) => <span key={share.share_id}>{share.platform === 'x' ? 'X' : '小红书'} · {share.status}</span>)}</section>
          <footer><button type="button" onClick={() => void toggleFavorite()}><Heart className={detail.project.favorite ? 'filled' : ''} />{detail.project.favorite ? '取消收藏' : '收藏项目'}</button><button type="button" onClick={() => void archiveProject()}><Archive />{detail.project.archived ? '恢复项目' : '归档项目'}</button></footer>
          {busyAction === 'detail' && <div className="detail-loading"><LoaderCircle className="spin" />读取项目</div>}
        </aside>}
      </div>
      {creating && <CreateProjectSheet onClose={() => setCreating(false)} onCreated={(snapshot) => { void handleProjectCreated(snapshot) }} />}
      {creatingFork && detail && <ForkProjectSheet project={detail.project} assets={detail.assets} onClose={() => setCreatingFork(false)} onCreated={() => { setCreatingFork(false); setDetail(null); setSelectedId(null); setNotice('扩展子项目已创建；父项目保持不变。'); void load() }} />}
      {sharePreview && <SharePreviewSheet preview={sharePreview} onClose={() => setSharePreview(null)} onComplete={(message) => { setSharePreview(null); setNotice(message); if (detail) void selectProject(detail.project) }} />}
    </main>
  )
}
