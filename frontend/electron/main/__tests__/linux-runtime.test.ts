import { afterEach, describe, expect, it, vi } from 'vitest'
import { configureLinuxRuntime } from '../linux-runtime'

function createApp(isPackaged = true, existingSwitches: string[] = []) {
    const switches = new Set(existingSwitches)
    const appendSwitch = vi.fn((name: string) => switches.add(name))
    return {
        app: {
            isPackaged,
            commandLine: {
                hasSwitch: (name: string) => switches.has(name),
                appendSwitch,
            },
        },
        appendSwitch,
    }
}

describe('configureLinuxRuntime', () => {
    afterEach(() => vi.restoreAllMocks())

    it('uses X11 and software rendering for a packaged Linux desktop session', () => {
        const { app, appendSwitch } = createApp()
        vi.spyOn(console, 'info').mockImplementation(() => undefined)

        configureLinuxRuntime(app, 'linux', { DISPLAY: ':0', WAYLAND_DISPLAY: 'wayland-0' })

        expect(appendSwitch.mock.calls).toEqual([
            ['disable-gpu'],
            ['ozone-platform', 'x11'],
        ])
    })

    it('keeps an explicitly selected ozone platform and adds software rendering', () => {
        const { app, appendSwitch } = createApp(true, ['ozone-platform'])
        vi.spyOn(console, 'info').mockImplementation(() => undefined)

        configureLinuxRuntime(app, 'linux', { DISPLAY: ':0' })

        expect(appendSwitch.mock.calls).toEqual([['disable-gpu']])
    })

    it('does not override explicit GPU options', () => {
        const { app, appendSwitch } = createApp(true, ['enable-gpu'])
        vi.spyOn(console, 'info').mockImplementation(() => undefined)

        configureLinuxRuntime(app, 'linux', { DISPLAY: ':0' })

        expect(appendSwitch.mock.calls).toEqual([['ozone-platform', 'x11']])
    })

    it('uses software rendering without selecting X11 when DISPLAY is unavailable', () => {
        const { app, appendSwitch } = createApp()
        vi.spyOn(console, 'info').mockImplementation(() => undefined)

        configureLinuxRuntime(app, 'linux', { WAYLAND_DISPLAY: 'wayland-0' })

        expect(appendSwitch.mock.calls).toEqual([['disable-gpu']])
    })

    it('does not change development or non-Linux runs', () => {
        vi.spyOn(console, 'info').mockImplementation(() => undefined)
        const developmentApp = createApp(false)
        const packagedApp = createApp(true)

        configureLinuxRuntime(developmentApp.app, 'linux', { DISPLAY: ':0' })
        configureLinuxRuntime(packagedApp.app, 'darwin', { DISPLAY: ':0' })

        expect(developmentApp.appendSwitch).not.toHaveBeenCalled()
        expect(packagedApp.appendSwitch).not.toHaveBeenCalled()
    })
})
