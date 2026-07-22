import { app, BrowserWindow, dialog, ipcMain, net, protocol, shell } from 'electron'
import { existsSync, mkdirSync, realpathSync, renameSync, rmSync } from 'node:fs'
import { homedir } from 'node:os'
import { isAbsolute, join, relative, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { randomUUID } from 'node:crypto'
import { ApsalFrontendBridge } from './apsal-link.mjs'
import { ApsalProtocolSidecar, APSAL_PROTOCOL_VERSION } from './apsal-protocol.mjs'
import { publishToWindow } from './safe-publish.mjs'
import { startupProjectRoot, wantsCodexLink } from './startup-args.mjs'

let mainWindow
let protocolSidecar
let frontendBridge
let currentProjectRoot
let isQuitting = false
const selectedMediaPaths = new Set()

protocol.registerSchemesAsPrivileged([{
  scheme: 'apsal-media',
  privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true },
}])

const PROTOCOL_MUTATIONS = new Set([
  'project.undo', 'design.propose', 'design.commit_preview', 'design.reject_preview',
  'analysis.start', 'analysis.record', 'design.build_from_analysis',
  'share.draft', 'share.confirm', 'share.publish',
])
const RENDERER_METHODS = new Set([
  'project.snapshot', 'project.undo', 'design.present',
  'design.propose', 'design.commit_preview', 'design.reject_preview',
  'project.fork', 'project.export',
  'analysis.start', 'analysis.next', 'analysis.status', 'design.build_from_analysis',
  'library.status', 'library.reconcile', 'library.list', 'library.get',
  'library.update', 'library.archive', 'library.lineage',
  'share.draft', 'share.preview', 'share.confirm', 'share.publish', 'share.status',
  'studio.view.get', 'studio.view.save',
])
const PROJECT_OPTIONAL_METHODS = new Set([
  'library.status', 'library.list', 'library.get', 'library.update', 'library.archive', 'library.lineage',
])

function publish(channel, value) {
  return publishToWindow(mainWindow, channel, value, { quitting: isQuitting })
}

function getSidecar() {
  if (!protocolSidecar) {
    protocolSidecar = new ApsalProtocolSidecar({
      appPath: app.getAppPath(),
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      onLog: (line) => process.stderr.write(`[apsal-engine] ${line}`),
      onExit: (value) => publish('apsal-protocol:status', value),
    })
  }
  return protocolSidecar
}

function getBridge() {
  if (!frontendBridge) {
    frontendBridge = new ApsalFrontendBridge({
      sidecar: getSidecar(),
      getProjectRoot: () => currentProjectRoot,
      onFocus: (value) => publish('apsal-protocol:focus', value),
      onChange: ({ method, result }) => {
        publish('apsal-protocol:change', { method, result })
        if (result?.snapshot) publish('apsal-protocol:snapshot', result.snapshot)
        void getBridge().status().then((value) => publish('apsal-link:status', value))
      },
    })
  }
  return frontendBridge
}

async function protocolStatus() {
  const sidecar = getSidecar().status()
  let snapshot
  if (currentProjectRoot && sidecar.running) {
    try {
      snapshot = await getSidecar().call('project.snapshot', { project_root: currentProjectRoot })
    } catch {
      // Preserve sidecar status even when the project is unreadable.
    }
  }
  return {
    ...sidecar,
    protocol_version: sidecar.protocol_version || APSAL_PROTOCOL_VERSION,
    project_root: currentProjectRoot,
    project_id: snapshot?.project?.project_id,
    session_id: snapshot?.session?.session_id,
    revision: snapshot?.revision,
  }
}

async function handleCodexLaunch(commandLine = process.argv) {
  const projectRoot = startupProjectRoot(commandLine)
  if (projectRoot) await openProjectRoot(projectRoot)
  if (wantsCodexLink(commandLine)) {
    if (!projectRoot && !currentProjectRoot) throw new Error('Codex 联动需要一个 APSAL 项目目录')
    const value = await getBridge().start()
    publish('apsal-link:status', value)
  }
}

async function openProjectRoot(projectRoot, mode = 'open') {
  const root = resolve(projectRoot)
  if (mode === 'open' && !existsSync(join(root, '.apsal', 'project.json'))) {
    throw new Error('所选目录不是 APSAL 项目；请选择包含 .apsal/project.json 的目录。')
  }
  const sidecar = getSidecar()
  const opened = await sidecar.call(mode === 'new' ? 'project.init' : 'project.open', { project_root: root })
  currentProjectRoot = root
  const snapshot = mode === 'new' ? await sidecar.call('project.snapshot', { project_root: root }) : opened
  if (snapshot?.compatible) {
    try {
      await sidecar.call('library.reconcile', { project_root: root })
    } catch (error) {
      process.stderr.write(`[apsal-studio] Could not reconcile opened project: ${error instanceof Error ? error.message : String(error)}\n`)
    }
  }
  publish('apsal-protocol:snapshot', snapshot)
  publish('apsal-protocol:status', await protocolStatus())
  publish('apsal-link:status', await getBridge().status())
  return snapshot
}

async function chooseReferenceImages() {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: '选择 APSAL 参考图片',
    buttonLabel: '加入参考组',
    properties: ['openFile', 'multiSelections'],
    filters: [{ name: '摄影图片', extensions: ['png', 'jpg', 'jpeg', 'webp'] }],
  })
  if (result.canceled) return []
  const paths = result.filePaths.slice(0, 24).map((value) => resolve(value))
  paths.forEach((value) => selectedMediaPaths.add(realpathSync(value)))
  return paths
}

function projectSlug(value) {
  return String(value || 'apsal-project')
    .normalize('NFKC')
    .replace(/[\\/:*?"<>|]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64) || 'apsal-project'
}

function projectsRoot() {
  const root = join(homedir(), 'APSAL Projects')
  mkdirSync(root, { recursive: true, mode: 0o700 })
  return root
}

async function activateProject(projectRoot, result, snapshotKey = 'snapshot') {
  currentProjectRoot = resolve(projectRoot)
  const snapshot = result?.[snapshotKey]
    || await getSidecar().call('project.snapshot', { project_root: currentProjectRoot })
  publish('apsal-protocol:snapshot', snapshot)
  publish('apsal-protocol:status', await protocolStatus())
  publish('apsal-link:status', await getBridge().status())
  return snapshot
}

async function createReferenceProject(input = {}) {
  const name = String(input.name || '').trim()
  const references = Array.isArray(input.references) ? input.references : []
  if (!name) throw new Error('请输入项目名称')
  if (references.length < 1 || references.length > 24) throw new Error('请选择 1–24 张参考图片')
  for (const item of references) {
    const path = realpathSync(resolve(String(item.path || '')))
    if (!selectedMediaPaths.has(path)) throw new Error('参考图片必须通过 APSAL Studio 选择')
  }
  const root = projectsRoot()
  const staging = join(root, `.creating-${randomUUID()}`)
  let target
  let targetCreated = false
  let operationCompleted = false
  try {
    const initialized = await getSidecar().call('project.init', { project_root: staging })
    const projectId = initialized?.project?.project_id
    if (!projectId) throw new Error('APSAL Engine 未返回项目 ID')
    target = join(root, `${projectSlug(name)}-${projectId}`)
    if (existsSync(target)) throw new Error(`项目目录已经存在：${target}`)
    renameSync(staging, target)
    targetCreated = true
    const result = await getSidecar().call('project.create_from_references', {
      project_root: target,
      name,
      references,
      expected_revision: 0,
      operation_id: `STUDIO-REFERENCE-${randomUUID()}`,
    })
    operationCompleted = true
    const snapshot = await activateProject(target, result)
    publish('apsal-protocol:change', { method: 'project.create_from_references', result })
    return { ...result, snapshot }
  } catch (error) {
    const incomplete = targetCreated ? target : staging
    if (!operationCompleted && existsSync(incomplete)) rmSync(incomplete, { recursive: true, force: true })
    throw error
  }
}

async function createForkProject(input = {}) {
  const name = String(input.name || '').trim()
  const parentRoot = resolve(String(input.parent_project_root || currentProjectRoot || ''))
  const forkType = String(input.fork_type || 'creative_expansion')
  const sourceAssetIds = Array.isArray(input.source_asset_ids)
    ? [...new Set(input.source_asset_ids.map((value) => String(value)).filter(Boolean))].slice(0, 24)
    : []
  if (!name) throw new Error('请输入子项目名称')
  if (!parentRoot || !existsSync(join(parentRoot, '.apsal', 'project.json'))) throw new Error('父项目不是有效的 APSAL 项目')
  const parent = await getSidecar().call('project.snapshot', { project_root: parentRoot })
  if (parent.read_only) throw new Error('旧版只读项目需要先复制迁移，再创建扩展子项目')
  const root = projectsRoot()
  const staging = join(root, `.forking-${randomUUID()}`)
  let target
  let targetCreated = false
  let operationCompleted = false
  try {
    const initialized = await getSidecar().call('project.init', { project_root: staging })
    const projectId = initialized?.project?.project_id
    if (!projectId) throw new Error('APSAL Engine 未返回子项目 ID')
    target = join(root, `${projectSlug(name)}-${projectId}`)
    if (existsSync(target)) throw new Error(`项目目录已经存在：${target}`)
    renameSync(staging, target)
    targetCreated = true
    const result = await getSidecar().call('project.fork', {
      project_root: parentRoot,
      target_project_root: target,
      name,
      fork_type: forkType,
      source_asset_ids: sourceAssetIds,
      expected_revision: parent.revision,
      operation_id: `STUDIO-FORK-${randomUUID()}`,
    })
    operationCompleted = true
    const snapshot = await activateProject(target, result, 'child_snapshot')
    publish('apsal-protocol:change', { method: 'project.fork', result: { ...result, snapshot } })
    return { ...result, snapshot }
  } catch (error) {
    const created = targetCreated ? target : staging
    if (!operationCompleted && existsSync(created)) rmSync(created, { recursive: true, force: true })
    throw error
  }
}

async function importProjectPackage() {
  const selection = await dialog.showOpenDialog(mainWindow, {
    title: '导入 APSAL 项目分享包',
    buttonLabel: '导入为新项目',
    properties: ['openFile'],
    filters: [{ name: 'APSAL 项目包', extensions: ['zip'] }],
  })
  if (selection.canceled || !selection.filePaths[0]) return null
  const source = realpathSync(selection.filePaths[0])
  const root = projectsRoot()
  const staging = join(root, `.importing-${randomUUID()}`)
  let target
  let targetCreated = false
  let operationCompleted = false
  try {
    const initialized = await getSidecar().call('project.init', { project_root: staging })
    const projectId = initialized?.project?.project_id
    if (!projectId) throw new Error('APSAL Engine 未返回导入项目 ID')
    const result = await getSidecar().call('project.import', { project_root: staging, source })
    operationCompleted = true
    target = join(root, `${projectSlug(result?.project?.name || 'imported-project')}-${projectId}`)
    if (existsSync(target)) throw new Error(`项目目录已经存在：${target}`)
    renameSync(staging, target)
    targetCreated = true
    await getSidecar().call('library.reconcile', { project_root: target })
    const snapshot = await activateProject(target, result)
    publish('apsal-protocol:change', { method: 'project.import', result: { ...result, project_root: target, snapshot } })
    return { ...result, project_root: target, snapshot }
  } catch (error) {
    const created = targetCreated ? target : staging
    if (!operationCompleted && existsSync(created)) rmSync(created, { recursive: true, force: true })
    throw error
  }
}

async function migrateCurrentProject() {
  if (!currentProjectRoot) throw new Error('请先打开需要迁移的 APSAL 0.15 项目')
  const sourceRoot = resolve(currentProjectRoot)
  const root = projectsRoot()
  const staging = join(root, `.migrating-${randomUUID()}`)
  let target
  let targetCreated = false
  let operationCompleted = false
  try {
    const preview = await getSidecar().call('project.migration_preview', {
      project_root: sourceRoot,
      target_project_root: staging,
    })
    const result = await getSidecar().call('project.migrate', {
      project_root: sourceRoot,
      target_project_root: staging,
      confirmed: true,
    })
    operationCompleted = true
    const projectId = result?.project?.project_id
    if (!projectId) throw new Error('APSAL Engine 未返回迁移项目 ID')
    target = join(root, `${projectSlug(result.project.name || 'migrated-project')}-${projectId}`)
    if (existsSync(target)) throw new Error(`迁移项目目录已经存在：${target}`)
    renameSync(staging, target)
    targetCreated = true
    await getSidecar().call('library.reconcile', { project_root: target })
    const snapshot = await activateProject(target, result)
    publish('apsal-protocol:change', { method: 'project.migrate', result: { ...result, preview, project_root: target, snapshot } })
    return { ...result, preview, project_root: target, snapshot }
  } catch (error) {
    const created = targetCreated ? target : staging
    if (!operationCompleted && existsSync(created)) rmSync(created, { recursive: true, force: true })
    throw error
  }
}

async function chooseProject(mode = 'open') {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: mode === 'new' ? '选择新的 APSAL 项目目录' : '打开 APSAL 项目目录',
    buttonLabel: mode === 'new' ? '在这里创建项目' : '打开项目',
    properties: ['openDirectory', 'createDirectory'],
  })
  if (result.canceled || !result.filePaths[0]) return null
  return openProjectRoot(result.filePaths[0], mode)
}

async function callProtocol(message = {}) {
  const method = String(message.method || '')
  if (!RENDERER_METHODS.has(method)) throw new Error(`Studio renderer is not allowed to call APSAL method: ${method}`)
  if (!currentProjectRoot && !PROJECT_OPTIONAL_METHODS.has(method)) throw new Error('请先新建或打开 APSAL 项目目录')
  const params = { ...(message.params || {}), project_root: currentProjectRoot || app.getPath('userData') }
  const result = await getSidecar().call(method, params)
  if (PROTOCOL_MUTATIONS.has(method) || method === 'studio.view.save') {
    publish('apsal-protocol:change', { method, result })
    if (result?.snapshot) publish('apsal-protocol:snapshot', result.snapshot)
  }
  return result
}

function isInside(child, parent) {
  const value = relative(parent, child)
  return value === '' || (!value.startsWith('..') && !isAbsolute(value))
}

function registerMediaProtocol() {
  protocol.handle('apsal-media', (request) => {
    const requested = new URL(request.url).searchParams.get('path')
    if (!requested) return new Response('Missing media path', { status: 400 })
    let mediaPath
    try {
      mediaPath = realpathSync(resolve(requested))
    } catch {
      return new Response('Media not found', { status: 404 })
    }
    const apsalHome = resolve(process.env.APSAL_HOME || join(homedir(), '.apsal'))
    const allowed = selectedMediaPaths.has(mediaPath)
      || isInside(mediaPath, join(apsalHome, 'library', 'objects'))
      || isInside(mediaPath, join(apsalHome, 'vault'))
    if (!allowed) return new Response('Media path is not allowed', { status: 403 })
    return net.fetch(pathToFileURL(mediaPath).toString())
  })
}

async function openExternal(urlValue) {
  const url = new URL(String(urlValue || ''))
  if (url.protocol !== 'https:' || !['x.com', 'creator.xiaohongshu.com'].includes(url.hostname)) {
    throw new Error('只允许打开 X 或小红书官方发布页面')
  }
  await shell.openExternal(url.toString())
  return { opened: true, url: url.toString() }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: '#0d0a08',
    title: 'APSAL Studio',
    show: false,
    webPreferences: {
      preload: join(app.getAppPath(), 'electron', 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  mainWindow.once('closed', () => { mainWindow = undefined })
  const devUrl = process.env.APSAL_STUDIO_DEV_URL
  if (devUrl) void mainWindow.loadURL(devUrl)
  else void mainWindow.loadFile(join(app.getAppPath(), 'dist', 'index.html'))
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.webContents.once('did-finish-load', () => {
    void protocolStatus().then((value) => publish('apsal-protocol:status', value))
    void getBridge().status().then((value) => publish('apsal-link:status', value))
    void handleCodexLaunch().catch((error) => {
      process.stderr.write(`[apsal-studio] Could not complete Codex launch: ${error instanceof Error ? error.message : String(error)}\n`)
    })
  })
}

function registerIpc() {
  ipcMain.handle('apsal-protocol:status', () => protocolStatus())
  ipcMain.handle('apsal-protocol:choose-project', (_event, mode) => chooseProject(mode))
  ipcMain.handle('apsal-protocol:open-project', (_event, projectRoot) => openProjectRoot(projectRoot))
  ipcMain.handle('apsal-protocol:choose-references', () => chooseReferenceImages())
  ipcMain.handle('apsal-protocol:create-reference-project', (_event, input) => createReferenceProject(input))
  ipcMain.handle('apsal-protocol:create-fork-project', (_event, input) => createForkProject(input))
  ipcMain.handle('apsal-protocol:import-project-package', () => importProjectPackage())
  ipcMain.handle('apsal-protocol:migrate-current-project', () => migrateCurrentProject())
  ipcMain.handle('apsal-protocol:call', (_event, message) => callProtocol(message))
  ipcMain.handle('apsal-protocol:open-external', (_event, url) => openExternal(url))
  ipcMain.handle('apsal-link:status', () => getBridge().status())
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', (_event, commandLine) => {
    void handleCodexLaunch(commandLine).catch((error) => {
      process.stderr.write(`[apsal-studio] Could not accept Codex launch ${JSON.stringify(commandLine)}: ${error instanceof Error ? error.message : String(error)}\n`)
    })
    if (!mainWindow) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  })
  app.whenReady().then(() => {
    app.setName('APSAL Studio')
    registerMediaProtocol()
    registerIpc()
    createWindow()
  })
}

app.on('before-quit', () => {
  isQuitting = true
  void frontendBridge?.stop()
  void protocolSidecar?.stop()
})
app.on('window-all-closed', () => app.quit())
