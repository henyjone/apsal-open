import { randomBytes, timingSafeEqual } from 'node:crypto'
import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:http'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { APSAL_PROTOCOL_VERSION } from './apsal-protocol.mjs'

const DESCRIPTOR_SCHEMA = '0.1.0'
const ALLOWED_METHODS = new Set([
  'project.init', 'project.open', 'project.snapshot', 'project.undo',
  'design.start', 'design.present', 'design.language', 'design.propose',
  'design.commit_preview', 'design.reject_preview', 'design.commit_layer',
  'design.finalize', 'finalize_theme',
  'generation.start', 'generation.next', 'generation.record', 'qa.record',
  'studio.view.get', 'studio.view.save', 'ui.focus_elements',
])
const MUTATING_METHODS = new Set([
  'project.init', 'project.undo', 'design.start', 'design.language', 'design.propose',
  'design.commit_preview', 'design.reject_preview', 'design.commit_layer',
  'design.finalize', 'finalize_theme', 'generation.start', 'generation.record', 'qa.record',
])

function json(response, status, value) {
  const payload = Buffer.from(JSON.stringify(value))
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': payload.length,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  })
  response.end(payload)
}

async function body(request) {
  const chunks = []
  let size = 0
  for await (const chunk of request) {
    size += chunk.length
    if (size > 1024 * 1024) throw new Error('request body exceeds 1 MiB')
    chunks.push(chunk)
  }
  const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8') || '{}')
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('request body must be a JSON object')
  return parsed
}

function secureEqual(left, right) {
  const a = Buffer.from(String(left || ''))
  const b = Buffer.from(String(right || ''))
  return a.length === b.length && a.length > 0 && timingSafeEqual(a, b)
}

export class ApsalFrontendBridge {
  constructor(options) {
    this.options = options
    this.server = undefined
    this.token = undefined
    this.descriptor = options.descriptorPath || join(homedir(), '.apsal', 'frontend-link.json')
    this.trust = options.trustPath || join(homedir(), '.apsal', 'frontend-trust.json')
    this.startedAt = undefined
  }

  async status() {
    const sidecar = this.options.sidecar.status()
    const projectRoot = this.options.getProjectRoot()
    let snapshot
    if (projectRoot && sidecar.running) {
      try {
        snapshot = await this.options.sidecar.call('project.snapshot', { project_root: projectRoot })
      } catch {
        // Status remains useful when the current project cannot be read.
      }
    }
    return {
      connected: Boolean(this.server && this.token && projectRoot && sidecar.compatible),
      enabled: Boolean(this.server),
      status: !this.server ? 'disabled' : !projectRoot ? 'no_project' : sidecar.compatible ? 'connected' : 'incompatible',
      protocol_version: APSAL_PROTOCOL_VERSION,
      engine_version: sidecar.engine_version,
      compatible: sidecar.compatible,
      project_root: projectRoot,
      project_id: snapshot?.project?.project_id,
      session_id: snapshot?.session?.session_id,
      revision: snapshot?.revision,
      started_at: this.startedAt,
    }
  }

  async start() {
    if (this.server) return this.status()
    await this.options.sidecar.start()
    this.token = randomBytes(32).toString('base64url')
    this.startedAt = new Date().toISOString()
    this.server = createServer((request, response) => { void this.#handle(request, response) })
    await new Promise((resolvePromise, reject) => {
      this.server.once('error', reject)
      this.server.listen(0, '127.0.0.1', resolvePromise)
    })
    const address = this.server.address()
    const baseUrl = `http://127.0.0.1:${address.port}`
    const directory = dirname(this.descriptor)
    mkdirSync(directory, { recursive: true, mode: 0o700 })
    chmodSync(directory, 0o700)
    writeFileSync(this.trust, `${JSON.stringify({ schema_version: DESCRIPTOR_SCHEMA, trusted: true, approved_at: this.startedAt })}\n`, { mode: 0o600 })
    writeFileSync(this.descriptor, `${JSON.stringify({
      schema_version: DESCRIPTOR_SCHEMA,
      pid: process.pid,
      base_url: baseUrl,
      token: this.token,
      protocol_version: APSAL_PROTOCOL_VERSION,
      started_at: this.startedAt,
    })}\n`, { mode: 0o600 })
    chmodSync(this.trust, 0o600)
    chmodSync(this.descriptor, 0o600)
    return this.status()
  }

  async #handle(request, response) {
    const supplied = request.headers.authorization?.replace(/^Bearer\s+/i, '')
    if (!secureEqual(supplied, this.token)) {
      return json(response, 401, { error: { code: 'unauthorized', message: 'invalid APSAL Studio link token' } })
    }
    try {
      if (request.method === 'GET' && request.url === '/v1/status') return json(response, 200, await this.status())
      if (request.method !== 'POST' || request.url !== '/v1/rpc') {
        return json(response, 404, { error: { code: 'not_found', message: 'unknown bridge route' } })
      }
      const message = await body(request)
      const method = String(message.method || '')
      if (!ALLOWED_METHODS.has(method)) {
        return json(response, 400, { error: { code: 'unknown_method', message: `unsupported APSAL bridge method: ${method}` } })
      }
      const projectRoot = this.options.getProjectRoot()
      if (!projectRoot) return json(response, 409, { error: { code: 'no_project', message: 'APSAL Studio has no current project' } })
      const params = message.params && typeof message.params === 'object' ? { ...message.params } : {}
      if (params.project_root && resolve(params.project_root) !== resolve(projectRoot)) {
        return json(response, 409, { error: { code: 'project_switched', message: 'requested project is not open in APSAL Studio' } })
      }
      params.project_root = projectRoot
      if (method === 'ui.focus_elements') {
        this.options.onFocus?.(params)
        return json(response, 200, { result: { focused: params.protocol_element_ids || [], preview_id: params.preview_id } })
      }
      const sidecar = this.options.sidecar.status()
      if (MUTATING_METHODS.has(method) && !sidecar.compatible) {
        return json(response, 409, { error: { code: 'protocol_incompatible', message: sidecar.error || 'APSAL protocol is read-only until upgraded' } })
      }
      const result = await this.options.sidecar.call(method, params)
      if (MUTATING_METHODS.has(method) || method === 'studio.view.save') this.options.onChange?.({ method, result })
      return json(response, 200, { result })
    } catch (error) {
      return json(response, 400, { error: { code: 'bridge_error', message: error instanceof Error ? error.message : String(error) } })
    }
  }

  async stop() {
    const server = this.server
    const token = this.token
    this.server = undefined
    this.token = undefined
    this.startedAt = undefined
    if (existsSync(this.descriptor)) {
      try {
        const current = JSON.parse(readFileSync(this.descriptor, 'utf8'))
        if (current.token === token) rmSync(this.descriptor, { force: true })
      } catch {
        // Do not delete a descriptor that cannot be authenticated as ours.
      }
    }
    if (server) await new Promise((resolvePromise) => server.close(resolvePromise))
  }
}
