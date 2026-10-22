import { createHash } from 'node:crypto'
import { cpSync, mkdirSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const studioRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(studioRoot, '..', '..')
const pluginRoot = join(repositoryRoot, 'plugins', 'apsal-studio')
const versionMap = JSON.parse(readFileSync(join(repositoryRoot, 'manifest', 'CURRENT_VERSION_MAP.json'), 'utf8'))
const studioPackage = JSON.parse(readFileSync(join(studioRoot, 'package.json'), 'utf8'))
const target = join(studioRoot, '.build', 'apsal-engine')
const enginePackage = 'apsal_engine'
const engineParts = 'apsal_engine_parts'
const scriptNames = ['apsal_creative.py', 'apsal_yaml.py', 'apsal_protocol.py', 'apsal_rpc.py']

const expectedEngine = versionMap.project_protocol.engine_version
const expectedProtocol = versionMap.project_protocol.version
const expectedStudio = versionMap.project_protocol.studio_version
const engineSource = readFileSync(join(pluginRoot, 'scripts', engineParts, 'constants.py'), 'utf8')
const protocolSource = readFileSync(join(pluginRoot, 'scripts', 'apsal_protocol.py'), 'utf8')
const engineVersion = engineSource.match(/^ENGINE_VERSION\s*=\s*"([^"]+)"/m)?.[1]
const protocolVersion = protocolSource.match(/^PROTOCOL_VERSION\s*=\s*"([^"]+)"/m)?.[1]

if (engineVersion !== expectedEngine || protocolVersion !== expectedProtocol || studioPackage.version !== expectedStudio) {
  throw new Error(`APSAL component version mismatch: Engine ${engineVersion}/${expectedEngine}, Protocol ${protocolVersion}/${expectedProtocol}, Studio package ${studioPackage.version}/map ${expectedStudio}`)
}

rmSync(target, { recursive: true, force: true })
mkdirSync(join(target, 'scripts'), { recursive: true })
cpSync(join(pluginRoot, 'assets'), join(target, 'assets'), { recursive: true })
const skipGenerated = (source) => !source.split(/[\\/]/).includes('__pycache__') && !source.endsWith('.pyc')
cpSync(join(pluginRoot, 'scripts', enginePackage), join(target, 'scripts', enginePackage), {
  recursive: true,
  filter: skipGenerated,
})
cpSync(join(pluginRoot, 'scripts', engineParts), join(target, 'scripts', engineParts), {
  recursive: true,
  filter: skipGenerated,
})
for (const name of scriptNames) cpSync(join(pluginRoot, 'scripts', name), join(target, 'scripts', name))

function pythonFiles(dir) {
  const found = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === '__pycache__' || entry.name.endsWith('.pyc')) continue
    const full = join(dir, entry.name)
    if (entry.isDirectory()) found.push(...pythonFiles(full))
    else if (entry.isFile() && entry.name.endsWith('.py')) found.push(full)
  }
  return found.sort()
}

const checksum = createHash('sha256')
for (const directory of [enginePackage, engineParts]) {
  for (const file of pythonFiles(join(target, 'scripts', directory))) checksum.update(readFileSync(file))
}
for (const name of scriptNames) checksum.update(readFileSync(join(target, 'scripts', name)))
writeFileSync(join(target, 'bundle.json'), `${JSON.stringify({
  schema_version: '0.1.0',
  source: 'apsal-open/plugins/apsal-studio',
  engine_version: engineVersion,
  protocol_version: protocolVersion,
  studio_version: expectedStudio,
  scripts_sha256: checksum.digest('hex'),
}, null, 2)}\n`)
