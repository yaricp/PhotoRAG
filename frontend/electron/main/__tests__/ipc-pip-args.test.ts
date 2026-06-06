import { describe, it, expect } from 'vitest'
import { buildInstallArgs } from '../ipc'

describe('buildInstallArgs', () => {
    it('includes CPU-only torch index on linux', () => {
        const args = buildInstallArgs('linux', '/path/to/requirements.txt')
        expect(args).toContain('--extra-index-url')
        expect(args).toContain('https://download.pytorch.org/whl/cpu')
    })

    it('includes CPU-only torch index on win32', () => {
        const args = buildInstallArgs('win32', '/path/to/requirements.txt')
        expect(args).toContain('--extra-index-url')
        expect(args).toContain('https://download.pytorch.org/whl/cpu')
    })

    it('does NOT include CPU-only index on darwin (Metal backend)', () => {
        const args = buildInstallArgs('darwin', '/path/to/requirements.txt')
        expect(args).not.toContain('--extra-index-url')
    })

    it('always includes -r <requirements> and --progress-bar off', () => {
        const args = buildInstallArgs('linux', '/my/req.txt')
        expect(args).toContain('-r')
        expect(args).toContain('/my/req.txt')
        expect(args).toContain('--progress-bar')
        expect(args).toContain('off')
    })
})
