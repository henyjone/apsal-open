import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import test from 'node:test'
import { ApsalFrontendBridge } from './apsal-link.mjs'
import { ApsalProtocolSidecar } from './apsal-protocol.mjs'

test('authenticated Codex bridge and direct sidecar share one idempotent project', async () => {
  const temporary = mkdtempSync(join(tmpdir(), 'apsal-link-test-'))
  const project = join(temporary, 'project')
  const descriptor = join(temporary, 'link', 'frontend-link.json')
  const trust = join(temporary, 'link', 'frontend-trust.json')
  const sidecar = new ApsalProtocolSidecar({ appPath: resolve('.'), isPackaged: false, resourcesPath: resolve('.build') })
  const bridge = new ApsalFrontendBridge({ sidecar, getProjectRoot: () => project, descriptorPath: descriptor, trustPath: trust })
  try {
    await sidecar.call('project.init', { project_root: project })
    await bridge.start()
    const first = JSON.parse(readFileSync(descriptor, 'utf8'))
    assert.equal(statSync(descriptor).mode & 0o777, 0o600)
    assert.equal((await fetch(`${first.base_url}/v1/status`)).status, 401)
    const headers = { Authorization: `Bearer ${first.token}`, 'Content-Type': 'application/json' }
    const status = await (await fetch(`${first.base_url}/v1/status`, { headers })).json()
    assert.equal(status.connected, true)

    const unknown = await fetch(`${first.base_url}/v1/rpc`, {
      method: 'POST', headers, body: JSON.stringify({ method: 'filesystem.read', params: {} }),
    })
    assert.equal(unknown.status, 400)

    const params = {
      brief: 'quiet window portrait', language: 'en', expected_revision: 0,
      operation_id: 'BRIDGE-START', theme_id: 'TEST-BRIDGE-015',
    }
    const linked = await (await fetch(`${first.base_url}/v1/rpc`, {
      method: 'POST', headers, body: JSON.stringify({ method: 'design.start', params }),
    })).json()
    assert.equal(linked.result.revision, 1)
    const direct = await sidecar.call('design.start', { project_root: project, ...params })
    assert.equal(direct.idempotent_replay, true)
    assert.deepEqual(direct.snapshot, linked.result.snapshot)

    await bridge.stop()
    assert.equal(existsSync(descriptor), false)
    assert.equal(existsSync(trust), true)
    await bridge.start()
    const second = JSON.parse(readFileSync(descriptor, 'utf8'))
    assert.notEqual(second.token, first.token)
  } finally {
    await bridge.stop()
    await sidecar.stop()
    rmSync(temporary, { recursive: true, force: true })
  }
})
