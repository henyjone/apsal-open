import { app, BrowserWindow, dialog, ipcMain } from 'electron'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { ApsalFrontendBridge } from './apsal-link.mjs'
import { ApsalProtocolSidecar, APSAL_PROTOCOL_VERSION } from './apsal-protocol.mjs'

let mainWindow
let protocolSidecar
let frontendBridge
let currentProjectRoot

const PROTOCOL_MUTATIONS = new Set([
  'project.undo', 'design.commit_preview', 'design.reject_preview',
])
const RENDERER_METHODS = new Set([
  'project.snapshot', 'project.undo', 'design.present',
  'design.commit_preview', 'design.reject_preview',
  'studio.view.get', 'studio.view.save',
])

function publish(channel, value) {
  mainWindow?.webContents.send(channel, value)
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

async function chooseProject(mode = 'open') {
  const result = await dialog.showOpenDialog(mainWindow, {
    title: mode === 'new' ? '选择新的 APSAL 项目目录' : '打开 APSAL 项目目录',
    buttonLabel: mode === 'new' ? '在这里创建项目' : '打开项目',
    properties: ['openDirectory', 'createDirectory'],
  })
  if (result.canceled || !result.filePaths[0]) return null
  const root = resolve(result.filePaths[0])
  if (mode === 'open' && !existsSync(join(root, '.apsal', 'project.json'))) {
    throw new Error('所选目录不是 APSAL 0.15 项目；旧 AiPhoto 项目不受支持。')
  }
  const sidecar = getSidecar()
  const opened = await sidecar.call(mode === 'new' ? 'project.init' : 'project.open', { project_root: root })
  currentProjectRoot = root
  const snapshot = mode === 'new' ? await sidecar.call('project.snapshot', { project_root: root }) : opened
  publish('apsal-protocol:snapshot', snapshot)
  publish('apsal-protocol:status', await protocolStatus())
  publish('apsal-link:status', await getBridge().status())
  return snapshot
}

async function callProtocol(message = {}) {
  const method = String(message.method || '')
  if (!RENDERER_METHODS.has(method)) throw new Error(`Studio renderer is not allowed to call APSAL method: ${method}`)
  if (!currentProjectRoot) throw new Error('请先新建或打开 APSAL 项目目录')
  const params = { ...(message.params || {}), project_root: currentProjectRoot }
  const result = await getSidecar().call(method, params)
  if (PROTOCOL_MUTATIONS.has(method) || method === 'studio.view.save') {
    publish('apsal-protocol:change', { method, result })
    if (result?.snapshot) publish('apsal-protocol:snapshot', result.snapshot)
  }
  return result
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1480,
    height: 940,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: '#0b1110',
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
  const devUrl = process.env.APSAL_STUDIO_DEV_URL
  if (devUrl) void mainWindow.loadURL(devUrl)
  else void mainWindow.loadFile(join(app.getAppPath(), 'dist', 'index.html'))
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.webContents.once('did-finish-load', () => {
    void protocolStatus().then((value) => publish('apsal-protocol:status', value))
    void getBridge().status().then((value) => publish('apsal-link:status', value))
  })
}

function registerIpc() {
  ipcMain.handle('apsal-protocol:status', () => protocolStatus())
  ipcMain.handle('apsal-protocol:choose-project', (_event, mode) => chooseProject(mode))
  ipcMain.handle('apsal-protocol:call', (_event, message) => callProtocol(message))
  ipcMain.handle('apsal-link:status', () => getBridge().status())
  ipcMain.handle('apsal-link:set-enabled', async (_event, enabled) => {
    const bridge = getBridge()
    const value = enabled ? await bridge.start() : await bridge.stop().then(() => bridge.status())
    publish('apsal-link:status', value)
    return value
  })
}

const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (!mainWindow) return
    if (mainWindow.isMinimized()) mainWindow.restore()
    mainWindow.focus()
  })
  app.whenReady().then(() => {
    app.setName('APSAL Studio')
    registerIpc()
    createWindow()
  })
}

app.on('before-quit', () => {
  void frontendBridge?.stop()
  void protocolSidecar?.stop()
})
app.on('window-all-closed', () => app.quit())
