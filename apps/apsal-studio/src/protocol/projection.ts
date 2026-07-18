import type {
  ApsalLayerId,
  ApsalProjectSnapshot,
  ApsalProtocolAttribute,
  ApsalProtocolElement,
  ApsalStudioView,
} from './types'

export const LAYERS: Array<{ id: ApsalLayerId; label: string; short: string }> = [
  { id: 'direction', label: '方向', short: 'Direction' },
  { id: 'worldbuilding', label: '世界构建', short: 'World' },
  { id: 'narrative', label: '叙事', short: 'Narrative' },
  { id: 'image', label: '影像', short: 'Image' },
  { id: 'delivery', label: '交付', short: 'Delivery' },
]

const LAYER_X: Record<ApsalLayerId, number> = {
  direction: 48,
  worldbuilding: 348,
  narrative: 648,
  image: 948,
  delivery: 1248,
}

export interface ProjectedNode {
  id: string
  protocolElementId: string
  previewId?: string
  layerId: ApsalLayerId
  roleId: string
  label: string
  status: string
  intent: string
  attributes: ApsalProtocolAttribute[]
  observable: string[]
  mustPreserve: string[]
  qaExpectations: string[]
  ghost: boolean
  participatesInPrompt: boolean
  x: number
  y: number
}

function projectedNode(element: ApsalProtocolElement, view?: ApsalStudioView, previewId?: string): ProjectedNode {
  const ghost = element.ghost === true || Boolean(previewId)
  const semanticId = element.protocol_element_id
  const stored = view?.nodes?.[semanticId]
  const layerOrder = Math.max(0, (element.order % 100) / 10)
  const position = stored ?? { x: LAYER_X[element.layer_id], y: 90 + layerOrder * 158 }
  const actualPreviewId = element.preview_id || previewId
  return {
    id: ghost ? element.preview_element_id || `ghost:${actualPreviewId}:${semanticId}` : semanticId,
    protocolElementId: semanticId,
    previewId: actualPreviewId,
    layerId: element.layer_id,
    roleId: element.role_id,
    label: element.label,
    status: element.status,
    intent: element.intent,
    attributes: element.attributes,
    observable: element.observable,
    mustPreserve: element.must_preserve,
    qaExpectations: element.qa_expectations,
    ghost,
    participatesInPrompt: element.participatesInPrompt !== false && !ghost,
    x: position.x + (ghost ? 24 : 0),
    y: position.y + (ghost ? 24 : 0),
  }
}

export function projectSnapshot(
  snapshot: ApsalProjectSnapshot,
  view?: ApsalStudioView | null,
): ProjectedNode[] {
  const nodes = snapshot.elements
    .filter((element) => element.ghost !== true)
    .map((element) => projectedNode(element, view ?? undefined))
  return nodes.sort((left, right) => {
    const layerDifference = LAYERS.findIndex((layer) => layer.id === left.layerId) - LAYERS.findIndex((layer) => layer.id === right.layerId)
    if (layerDifference !== 0) return layerDifference
    if (left.ghost !== right.ghost) return left.ghost ? 1 : -1
    return left.y - right.y
  })
}

export function nodesToStudioView(
  nodes: ProjectedNode[],
  selectedElementId: string | null,
  zoom = 1,
): Omit<ApsalStudioView, 'schema_version' | 'view_revision'> {
  return {
    nodes: Object.fromEntries(
      nodes
        .filter((node) => !node.ghost)
        .map((node) => [node.protocolElementId, { x: node.x, y: node.y, collapsed: false }]),
    ),
    viewport: { x: 0, y: 0, zoom },
    selected_element_id: selectedElementId,
    expanded_cards: selectedElementId ? [selectedElementId] : [],
  }
}
