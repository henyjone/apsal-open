import assert from 'node:assert/strict'
import test from 'node:test'
import { publishToWindow } from './safe-publish.mjs'

test('publish skips destroyed or quitting Electron windows without throwing', () => {
  const sent = []
  const liveWindow = {
    isDestroyed: () => false,
    webContents: {
      isDestroyed: () => false,
      send: (...message) => sent.push(message),
    },
  }

  assert.equal(publishToWindow(liveWindow, 'apsal:test', { revision: 2 }), true)
  assert.deepEqual(sent, [['apsal:test', { revision: 2 }]])
  assert.equal(publishToWindow(liveWindow, 'apsal:test', {}, { quitting: true }), false)
  assert.equal(publishToWindow({ isDestroyed: () => true }, 'apsal:test', {}), false)
  assert.equal(publishToWindow({
    isDestroyed: () => false,
    webContents: { isDestroyed: () => true },
  }, 'apsal:test', {}), false)
  assert.equal(publishToWindow({
    isDestroyed: () => { throw new TypeError('Object has been destroyed') },
  }, 'apsal:test', {}), false)
})
