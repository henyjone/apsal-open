import { describe, expect, it } from 'vitest'
import { nodesToStudioView, projectSnapshot, projectWorkflowEdges } from './projection'
import type { ApsalLayerId, ApsalPreview, ApsalProjectSnapshot } from './types'

function snapshot(): ApsalProjectSnapshot {
  const roles = [
    ['direction', 'content'], ['direction', 'emotion'],
    ['worldbuilding', 'subject'], ['worldbuilding', 'world'], ['worldbuilding', 'look'],
    ['narrative', 'event'], ['narrative', 'sequence'],
    ['image', 'camera'], ['image', 'light'], ['image', 'style'], ['image', 'color_post'],
    ['delivery', 'job'], ['delivery', 'quality_control'],
  ] as Array<[ApsalLayerId, string]>
  return {
    project_root: '/tmp/project',
    project: { project_id: 'PROJECT-TEST', protocol_version: '0.16.0', engine_version: '0.16.0', revision: 4 },
    compatible: true,
    read_only: false,
    revision: 4,
    protocol_version: '0.16.0',
    engine_version: '0.16.0',
    session: null,
    elements: roles.map(([layer, role], index) => ({
      protocol_element_id: `THEME:${role}`,
      ghost: false,
      participatesInPrompt: true,
      layer_id: layer,
      role_id: role,
      label: role,
      studio_type: 'custom_prompt',
      status: 'proposed',
      intent: role,
      attributes: [{ id: `THEME:${role}:value`, name: 'value', value: role }],
      observable: [],
      must_preserve: [],
      qa_expectations: [],
      order: index * 10,
    })),
    previews: [],
    stage_previews: [],
  }
}

describe('APSAL Studio projection', () => {
  it('keeps all thirteen stable roles and persists geometry only', () => {
    const nodes = projectSnapshot(snapshot())
    expect(nodes).toHaveLength(13)
    expect(new Set(nodes.map((node) => node.protocolElementId)).size).toBe(13)
    expect(nodes.every((node) => node.studioType === 'custom_prompt')).toBe(true)
    expect(projectWorkflowEdges(nodes)).toHaveLength(12)
    nodes[0].x = 777
    nodes[0].y = 333
    const view = nodesToStudioView(nodes, nodes[0].protocolElementId, { x: 48, y: 36, zoom: 0.72 })
    expect(view.nodes[nodes[0].protocolElementId]).toEqual({ x: 777, y: 333, collapsed: false })
    expect(view.viewport).toEqual({ x: 48, y: 36, zoom: 0.72 })
    expect(JSON.stringify(view)).not.toContain('intent')
    expect(JSON.stringify(view)).not.toContain('value')
  })

  it('keeps pending previews in the side panel without duplicating canvas nodes', () => {
    const source = snapshot()
    const preview: ApsalPreview = {
      preview_id: 'PREVIEW-1',
      operation_id: 'OP-1',
      session_id: 'SESSION-1',
      layer: 'direction',
      base_revision: 4,
      revision: 4,
      status: 'pending',
      invalidates_if_applied: ['worldbuilding'],
      elements: source.elements.filter((element) => element.layer_id === 'direction').map((element) => ({
        ...element,
        ghost: true,
        participatesInPrompt: false,
        preview_id: 'PREVIEW-1',
        preview_element_id: `PREVIEW-1:${element.role_id}`,
      })),
    }
    source.previews = [preview]
    source.elements.push(preview.elements[0])
    const nodes = projectSnapshot(source)
    expect(nodes).toHaveLength(13)
    expect(nodes.some((node) => node.ghost)).toBe(false)
    expect(source.previews).toHaveLength(1)
  })
})
