import { createHash } from 'node:crypto'
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const studioRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(studioRoot, '..', '..')
const pluginRoot = join(repositoryRoot, 'plugins', 'apsal-studio')
const versionMap = JSON.parse(readFileSync(join(repositoryRoot, 'manifest', 'CURRENT_VERSION_MAP.json'), 'utf8'))
const target = join(studioRoot, '.build', 'apsal-engine')
const scriptNames = ['apsal_engine.py', 'apsal_creative.py', 'apsal_yaml.py', 'apsal_protocol.py', 'apsal_rpc.py']

const expectedEngine = versionMap.project_protocol.engine_version
const expectedProtocol = versionMap.project_protocol.version
const expectedStudio = versionMap.project_protocol.studio_version
const engineSource = readFileSync(join(pluginRoot, 'scripts', 'apsal_engine.py'), 'utf8')
const protocolSource = readFileSync(join(pluginRoot, 'scripts', 'apsal_protocol.py'), 'utf8')
const engineVersion = engineSource.match(/^ENGINE_VERSION\s*=\s*"([^"]+)"/m)?.[1]
const protocolVersion = protocolSource.match(/^PROTOCOL_VERSION\s*=\s*"([^"]+)"/m)?.[1]

if (engineVersion !== expectedEngine || protocolVersion !== expectedProtocol || expectedStudio !== '0.3.0') {
  throw new Error(`APSAL component version mismatch: Engine ${engineVersion}/${expectedEngine}, Protocol ${protocolVersion}/${expectedProtocol}, Studio ${expectedStudio}/0.3.0`)
}

rmSync(target, { recursive: true, force: true })
mkdirSync(join(target, 'scripts'), { recursive: true })
cpSync(join(pluginRoot, 'assets'), join(target, 'assets'), { recursive: true })
for (const name of scriptNames) cpSync(join(pluginRoot, 'scripts', name), join(target, 'scripts', name))

const checksum = createHash('sha256')
for (const name of scriptNames) checksum.update(readFileSync(join(target, 'scripts', name)))
writeFileSync(join(target, 'bundle.json'), `${JSON.stringify({
  schema_version: '0.1.0',
  source: 'apsal-open/plugins/apsal-studio',
  engine_version: engineVersion,
  protocol_version: protocolVersion,
  studio_version: expectedStudio,
  scripts_sha256: checksum.digest('hex'),
}, null, 2)}\n`)
