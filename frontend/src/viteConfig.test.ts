/**
 * @vitest-environment node
 */
import { describe, expect, it } from 'vitest'

import config from '../vite.config'

describe('vite dev server config', () => {
  it('allows the configured public domain used for LAN access', () => {
    expect(config.server?.allowedHosts).toContain('fojing.art')
  })
})
