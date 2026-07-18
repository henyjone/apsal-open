import assert from 'node:assert/strict'
import test from 'node:test'
import { startupProjectRoot, wantsCodexLink } from './startup-args.mjs'

test('startup arguments accept normal and macOS second-instance ordering', () => {
  const project = '/Users/test/APSAL Project'
  assert.equal(startupProjectRoot(['APSAL Studio', '--project-root', project, '--codex-link']), project)
  assert.equal(startupProjectRoot(['APSAL Studio', `--project-root=${project}`, '--codex-link']), project)
  assert.equal(
    startupProjectRoot([
      'APSAL Studio', '--project-root', '--codex-link', '--allow-file-access-from-files',
      '--enable-avfoundation', project,
    ]),
    project,
  )
  assert.equal(startupProjectRoot(['APSAL Studio', '--codex-link']), undefined)
  assert.equal(wantsCodexLink(['APSAL Studio', '--codex-link']), true)
})
