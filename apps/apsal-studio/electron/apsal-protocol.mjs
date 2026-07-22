import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { createInterface } from 'node:readline'

export const APSAL_PROTOCOL_VERSION = '0.16.0'
export const APSAL_ENGINE_VERSION = '0.16.0'

function engineBundleRoot({ appPath, isPackaged, resourcesPath }) {
  if (process.env.APSAL_ENGINE_ROOT) return resolve(process.env.APSAL_ENGINE_ROOT)
  return isPackaged ? join(resourcesPath, 'apsal-engine') : resolve(appPath, '.build', 'apsal-engine')
}

function pythonCommand(resourcesPath) {
  const bundled = join(resourcesPath, 'python', 'bin', 'python3')
  if (existsSync(bundled)) return bundled
  if (process.env.APSAL_PYTHON) return process.env.APSAL_PYTHON
  return existsSync('/usr/bin/python3') ? '/usr/bin/python3' : 'python3'
}

export class ApsalProtocolSidecar {
  constructor(options) {
    this.options = options
    this.process = undefined
    this.readyPromise = undefined
    this.nextId = 1
    this.pending = new Map()
    this.info = {
      running: false,
      compatible: false,
      protocol_version: APSAL_PROTOCOL_VERSION,
      engine_version: APSAL_ENGINE_VERSION,
      error: null,
    }
  }

  status() {
    return { ...this.info }
  }

  async start() {
    if (this.readyPromise) return this.readyPromise
    if (this.process && this.info.running) return this.status()
    this.readyPromise = this.#startProcess().finally(() => { this.readyPromise = undefined })
    return this.readyPromise
  }

  async #startProcess() {
    const root = engineBundleRoot(this.options)
    const rpc = join(root, 'scripts', 'apsal_rpc.py')
    if (!existsSync(rpc)) throw new Error(`APSAL Engine sidecar missing: ${rpc}`)
    const child = spawn(pythonCommand(this.options.resourcesPath), ['-u', rpc], {
      cwd: join(root, 'scripts'),
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    this.process = child
    this.info = { ...this.info, running: true, compatible: false, error: null, pid: child.pid, root }
    createInterface({ input: child.stdout }).on('line', (line) => this.#consumeLine(line))
    child.stderr.on('data', (chunk) => this.options.onLog?.(chunk.toString()))
    child.once('error', (error) => this.#handleExit(error))
    child.once('exit', (code, signal) => this.#handleExit(new Error(`APSAL Engine sidecar exited: code=${code ?? '?'} signal=${signal ?? '?'}`)))
    const hello = await this.#request('initialize', {}, 10_000)
    const compatible = hello.protocol_version === APSAL_PROTOCOL_VERSION && hello.engine_version === APSAL_ENGINE_VERSION
    this.info = {
      ...this.info,
      running: true,
      compatible,
      protocol_version: hello.protocol_version,
      engine_version: hello.engine_version,
      error: compatible ? null : `Protocol mismatch: Studio ${APSAL_PROTOCOL_VERSION}, Engine ${hello.protocol_version}`,
    }
    return this.status()
  }

  async call(method, params = {}, timeoutMs = 30_000) {
    await this.start()
    if (!this.info.compatible && !['ping', 'project.open', 'project.snapshot', 'studio.view.get'].includes(method)) {
      throw new Error(this.info.error || 'APSAL Engine protocol is read-only until upgraded')
    }
    return this.#request(method, params, timeoutMs)
  }

  #request(method, params, timeoutMs) {
    if (!this.process?.stdin.writable) return Promise.reject(new Error('APSAL Engine sidecar is not running'))
    const id = this.nextId++
    return new Promise((resolvePromise, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`APSAL Engine call timed out: ${method}`))
      }, timeoutMs)
      this.pending.set(id, { resolve: resolvePromise, reject, timer, method })
      this.process.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`)
    })
  }

  #consumeLine(line) {
    let message
    try {
      message = JSON.parse(line)
    } catch {
      this.options.onLog?.(`sidecar stdout is not JSON: ${line}\n`)
      return
    }
    const pending = this.pending.get(message.id)
    if (!pending) return
    clearTimeout(pending.timer)
    this.pending.delete(message.id)
    if (message.error) pending.reject(new Error(message.error.message || `APSAL Engine ${pending.method} failed`))
    else pending.resolve(message.result)
  }

  #handleExit(error) {
    this.process = undefined
    this.info = { ...this.info, running: false, compatible: false, pid: undefined, error: error.message }
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer)
      pending.reject(error)
    }
    this.pending.clear()
    this.options.onExit?.(this.status())
  }

  async stop() {
    const child = this.process
    if (!child) return
    this.process = undefined
    child.stdin.end()
    child.kill('SIGTERM')
    await new Promise((resolvePromise) => {
      const timer = setTimeout(() => {
        if (child.exitCode == null) child.kill('SIGKILL')
        resolvePromise()
      }, 2500)
      child.once('exit', () => { clearTimeout(timer); resolvePromise() })
    })
  }
}
