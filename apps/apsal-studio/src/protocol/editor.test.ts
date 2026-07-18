import { describe, expect, it } from 'vitest'
import { buildStudioEdit, createStudioEditDraft } from './editor'
import type { ProjectedNode } from './projection'

function node(): ProjectedNode {
  return {
    id: 'THEME:content',
    protocolElementId: 'THEME:content',
    layerId: 'direction',
    roleId: 'content',
    studioType: 'global_control',
    label: '创作命题',
    status: 'proposed',
    intent: '把简报变成明确的摄影命题',
    rawIntent: 'Turn the brief into a concrete photographic proposition.',
    attributes: [
      { id: 'THEME:content:shot_count', key: 'shot_count', name: '镜头数量', value: '9', raw_value: 9 },
      { id: 'THEME:content:chapters', key: 'chapters', name: '章节', value: '["开场"]', raw_value: ['开场'] },
    ],
    observable: [],
    mustPreserve: [],
    qaExpectations: [],
    ghost: false,
    participatesInPrompt: true,
    x: 0,
    y: 0,
  }
}

describe('Studio semantic editor', () => {
  it('does not turn localized display copy into a change until the creator edits it', () => {
    const selected = node()
    expect(buildStudioEdit(selected, createStudioEditDraft(selected))).toEqual({ decision: {}, changes: [] })
  })

  it('creates a typed, partial protocol decision and a readable diff', () => {
    const selected = node()
    const draft = createStudioEditDraft(selected)
    draft.intent = '让创作命题围绕雨夜重逢展开'
    draft.values.shot_count = '12'
    draft.values.chapters = '["相遇", "转折", "余韵"]'
    const result = buildStudioEdit(selected, draft)
    expect(result.decision).toEqual({
      intent: '让创作命题围绕雨夜重逢展开',
      values: { shot_count: 12, chapters: ['相遇', '转折', '余韵'] },
    })
    expect(result.changes).toHaveLength(3)
  })

  it('rejects malformed structured values before they reach the Engine', () => {
    const selected = node()
    const draft = createStudioEditDraft(selected)
    draft.values.chapters = '不是 JSON'
    expect(() => buildStudioEdit(selected, draft)).toThrow('有效 JSON')
  })
})
