import { describe, expect, it } from 'vitest'
import { readFileSync } from 'fs'
import { join } from 'path'

const packageJson = JSON.parse(
    readFileSync(join(process.cwd(), 'package.json'), 'utf8')
)

describe('Windows package config', () => {
    it('builds x64 and arm64 installers separately so the bundled Python runtime matches the app arch', () => {
        expect(packageJson.scripts['dist:win']).toContain('nsis:x64')
        expect(packageJson.scripts['dist:win']).not.toContain('arm64')
        expect(packageJson.scripts['dist:win:arm64']).toContain('nsis:arm64')
        expect(packageJson.build.win.target).toEqual(['nsis'])
    })
})
