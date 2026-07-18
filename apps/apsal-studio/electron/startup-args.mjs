export function startupProjectRoot(commandLine = []) {
  const inline = commandLine.find((value) => value.startsWith('--project-root='))
  if (inline) return inline.slice('--project-root='.length)
  const index = commandLine.indexOf('--project-root')
  if (index < 0) return undefined
  return commandLine.slice(index + 1).find((value) => value && !value.startsWith('-'))
}

export function wantsCodexLink(commandLine = []) {
  return commandLine.includes('--codex-link')
}
