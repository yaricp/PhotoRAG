import { describe, it, expect } from 'vitest'
import { buildDownloadScript, buildInstallArgs } from '../ipc'

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
        expect(args[0]).toBe('install')
        expect(args).toContain('-r')
        expect(args).toContain('/my/req.txt')
        expect(args).toContain('--progress-bar')
        expect(args).toContain('off')
    })
})

describe('buildDownloadScript', () => {
    it('checks for missing Windows VC++ runtime before PyTorch-backed model setup', () => {
        const script = buildDownloadScript('clip')

        expect(script).toContain('check_windows_torch_runtime(model_id)')
        expect(script).toContain('import torch')
        expect(script).toContain('Microsoft Visual C++ Redistributable x64 is required')
        expect(script).toContain('https://aka.ms/vs/17/release/vc_redist.x64.exe')
        expect(script).toContain('c10.dll')
        expect(script).toContain('winerror == 126')
    })
})
