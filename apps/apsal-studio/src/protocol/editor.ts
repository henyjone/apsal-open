import type { ProjectedNode } from './projection'

export interface StudioEditDraft {
  intent: string
  values: Record<string, string>
}

export interface StudioEditChange {
  field: string
  label: string
  before: string
  after: string
}

export interface StudioEditResult {
  decision: { intent?: string; values?: Record<string, unknown> }
  changes: StudioEditChange[]
}

export function attributeKey(attribute: { id: string; key?: string }): string {
  return attribute.key || attribute.id.split(':').at(-1) || attribute.id
}

export function createStudioEditDraft(node: ProjectedNode): StudioEditDraft {
  return {
    intent: node.intent,
    values: Object.fromEntries(node.attributes.map((attribute) => [attributeKey(attribute), attribute.value])),
  }
}

function parsedValue(input: string, original: unknown): unknown {
  if (typeof original === 'string' || original === undefined) return input
  if (typeof original === 'number') {
    const value = Number(input)
    if (!Number.isFinite(value)) throw new Error('请输入有效数字')
    return value
  }
  if (typeof original === 'boolean') {
    const normalized = input.trim().toLowerCase()
    if (['true', '是', '开启', '启用'].includes(normalized)) return true
    if (['false', '否', '关闭', '停用'].includes(normalized)) return false
    throw new Error('布尔值请输入“是/否”或 true/false')
  }
  try {
    return JSON.parse(input)
  } catch {
    throw new Error('列表或结构属性必须填写有效 JSON')
  }
}

export function buildStudioEdit(node: ProjectedNode, draft: StudioEditDraft): StudioEditResult {
  const decision: StudioEditResult['decision'] = {}
  const changes: StudioEditChange[] = []
  if (draft.intent !== node.intent) {
    decision.intent = draft.intent
    changes.push({ field: 'intent', label: '元素意图', before: node.intent, after: draft.intent })
  }
  const values: Record<string, unknown> = {}
  for (const attribute of node.attributes) {
    const key = attributeKey(attribute)
    const input = draft.values[key] ?? ''
    if (input === attribute.value) continue
    values[key] = parsedValue(input, attribute.raw_value)
    changes.push({ field: `values.${key}`, label: attribute.name, before: attribute.value, after: input })
  }
  if (Object.keys(values).length > 0) decision.values = values
  return { decision, changes }
}
