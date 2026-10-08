import { chmodSync, copyFileSync, existsSync, linkSync, mkdirSync, readFileSync, renameSync, statSync, unlinkSync, writeFileSync } from 'fs'
import { copyFile } from 'fs/promises'
import { join, resolve } from 'path'
import { app } from 'electron'
import { logToFile } from './backend'

function quoteDesktopExecArg(value: string): string {
    const escaped = value
        .replace(/([\\`"$])/g, '\\$1')
        .replace(/%/g, '%%')
    return `"${escaped}"`
}

async function persistAppImage(source: string): Promise<string> {
    const applicationsDir = join(app.getPath('home'), 'Applications')
    const destination = join(applicationsDir, 'PhotoRAG.AppImage')
    if (resolve(source) === resolve(destination)) return destination

    const sourceStat = statSync(source)
    const metadata = {
        version: app.getVersion(),
        size: sourceStat.size,
        mtimeMs: sourceStat.mtimeMs,
    }
    const metadataPath = join(applicationsDir, '.photorag-appimage.json')

    mkdirSync(applicationsDir, { recursive: true })

    if (existsSync(destination)) {
        try {
            const current = JSON.parse(readFileSync(metadataPath, 'utf8')) as typeof metadata
            if (current.version === metadata.version && current.size === metadata.size && current.mtimeMs === metadata.mtimeMs) {
                return destination
            }
        } catch { /* Refresh an unmanaged or outdated copy. */ }
    }

    const temporary = `${destination}.tmp-${process.pid}`
    const temporaryMetadata = `${metadataPath}.tmp-${process.pid}`
    try {
        try {
            // A hard link avoids duplicating a large AppImage when Downloads and
            // Applications are on the same filesystem. Deleting the download
            // then leaves the Applications link intact.
            linkSync(source, temporary)
        } catch {
            // Different filesystems (or filesystems without hard-link support)
            // need a normal copy. Keep it asynchronous so startup remains responsive.
            await copyFile(source, temporary)
            chmodSync(temporary, 0o755)
        }
        renameSync(temporary, destination)
        writeFileSync(temporaryMetadata, JSON.stringify(metadata), { mode: 0o600 })
        renameSync(temporaryMetadata, metadataPath)
        logToFile(`[startup] kept AppImage in Applications: ${destination}`)
        return destination
    } catch (error) {
        try { unlinkSync(temporary) } catch { /* Ignore a missing temporary file. */ }
        try { unlinkSync(temporaryMetadata) } catch { /* Ignore a missing temporary file. */ }
        throw error
    }
}

/** Keep a persistent per-user AppImage copy and register it in the desktop menu. */
export async function ensureLinuxAppMenuEntry(): Promise<void> {
    if (process.platform !== 'linux' || !app.isPackaged) return

    // AppImage runtimes expose APPIMAGE as the absolute path to the original file.
    const appImagePath = process.env.APPIMAGE
    if (!appImagePath) return

    const sourceAppImage = resolve(appImagePath)
    if (!existsSync(sourceAppImage) || /[\r\n]/.test(sourceAppImage)) {
        logToFile('[startup] skipped application-menu entry: AppImage path is unavailable')
        return
    }

    let executable = sourceAppImage
    try {
        executable = await persistAppImage(sourceAppImage)
    } catch (error) {
        logToFile(`[startup] could not keep AppImage in Applications: ${error instanceof Error ? error.message : String(error)}`)
    }

    const dataHome = process.env.XDG_DATA_HOME || join(app.getPath('home'), '.local', 'share')
    const applicationsDir = join(dataHome, 'applications')
    const desktopPath = join(applicationsDir, 'com.photorag.app.desktop')

    let icon = 'applications-graphics'
    const bundledIcon = join(process.resourcesPath, 'photorag-icon.png')
    if (existsSync(bundledIcon)) {
        try {
            const iconPath = join(dataHome, 'icons', 'com.photorag.app.png')
            mkdirSync(join(dataHome, 'icons'), { recursive: true })
            copyFileSync(bundledIcon, iconPath)
            icon = iconPath
        } catch (error) {
            logToFile(`[startup] could not install application icon: ${error instanceof Error ? error.message : String(error)}`)
        }
    }

    const execArgs = [executable]
    for (const switchName of ['disable-gpu', 'enable-gpu', 'ozone-platform', 'ozone-platform-hint']) {
        if (!app.commandLine.hasSwitch(switchName)) continue
        const value = app.commandLine.getSwitchValue(switchName)
        execArgs.push(value ? `--${switchName}=${value}` : `--${switchName}`)
    }

    const desktopEntry = [
        '[Desktop Entry]',
        'Version=1.0',
        'Type=Application',
        'Name=PhotoRAG',
        'Comment=Browse and search your photo library',
        `Exec=${execArgs.map(quoteDesktopExecArg).join(' ')}`,
        `Icon=${icon}`,
        'Terminal=false',
        'Categories=Graphics;Photography;',
        'StartupWMClass=com.photorag.app',
        '',
    ].join('\n')

    try {
        mkdirSync(applicationsDir, { recursive: true })
        writeFileSync(desktopPath, desktopEntry, { mode: 0o755 })
        chmodSync(desktopPath, 0o755)
        logToFile('[startup] added PhotoRAG to the current user application menu')
    } catch (error) {
        logToFile(`[startup] could not add application-menu entry: ${error instanceof Error ? error.message : String(error)}`)
    }
}
