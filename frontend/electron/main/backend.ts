import { spawn, ChildProcess } from 'child_process'
import { app } from 'electron'
import path from 'path'
import net from 'net'

let backendProcess: ChildProcess | null = null

export async function findFreePort(start = 8000): Promise<number> {
    return new Promise((resolve, reject) => {
        const server = net.createServer()
        server.listen(start, () => {
            const addr = server.address()
            const port = typeof addr === 'object' && addr ? addr.port : start
            server.close(() => resolve(port))
        })
        server.on('error', () => {
            findFreePort(start + 1).then(resolve).catch(reject)
        })
    })
}

async function waitForBackend(port: number, retries = 20): Promise<void> {
    for (let i = 0; i < retries; i++) {
        try {
            const res = await fetch(`http://localhost:${port}/api/system/status/`)
            if (res.ok) return
        } catch {
            // not ready yet
        }
        await new Promise(r => setTimeout(r, 500))
    }
    throw new Error(`Backend did not start on port ${port}`)
}

// export async function startBackend(): Promise<number> {
//     const port = await findFreePort()
//     const userData = app.getPath('userData')

//     const backendExe = app.isPackaged
//         ? path.join(process.resourcesPath, 'backend', 'run')
//         : 'python'

//     const args = app.isPackaged
//         ? [`--port=${port}`, `--db-path=${userData}/photos.sqlite3`]
//         : ['-m', 'uvicorn', 'src.main:app', '--port', String(port), '--reload']

//     backendProcess = spawn(backendExe, args, {
//         cwd: app.isPackaged
//             ? undefined
//             : path.join(__dirname, '../../../backend'),
//         env: {
//             ...process.env,
//             WATCH_DIRECTORY: path.join(userData, 'photos'),
//         },
//     })

//     backendProcess.stdout?.on('data', (d) => console.log('[backend]', d.toString()))
//     backendProcess.stderr?.on('data', (d) => console.error('[backend]', d.toString()))

//     backendProcess.on('exit', (code) => {
//         console.log(`[backend] exited with code ${code}`)
//         backendProcess = null
//     })

//     await waitForBackend(port)
//     return port
// }

export async function startBackend(): Promise<number> {
    console.log('[backend] using external backend on port 8000')
    return 8000
}

export function stopBackend(): void {
    backendProcess?.kill()
    backendProcess = null
}