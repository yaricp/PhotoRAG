import React, { useEffect, useState } from 'react'
import {
    getWatchers,
    addWatcher,
    deleteWatcher,
    getFolderScanners,
    addFolderScanner,
    deleteFolderScanner,
} from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { FolderSelector } from '@/components/ui/FolderSelector'
import type { FolderScanner, Watcher } from '@/types/api'
import './FoldersPage.css'


export function FoldersPage() {
    const [watchers, setWatchers] = useState<Watcher[]>([])
    const [scanners, setScanners] = useState<FolderScanner[]>([])
    const [loading, setLoading] = useState(true)

    const [newPathWatcher, setNewPathWatcher] = useState('')
    const [newDestinationPathWatcher, setNewDestinationPathWatcher] = useState('')
    const [addingWatcher, setAddingWatcher] = useState(false)

    const [newPathScanner, setNewPathScanner] = useState('')
    const [addingScanner, setAddingScanner] = useState(false)

    const load = async () => {
        try {
            const data_watchers = await getWatchers()
            const data_scanners = await getFolderScanners()
            setWatchers(data_watchers)
            setScanners(data_scanners)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        load()
        const interval = setInterval(load, 5000)
        return () => clearInterval(interval)
    }, [])

    const handleAddWatcher = async () => {
        if (!newPathWatcher.trim()) return

        setAddingWatcher(true)
        try {
            const watcher = await addWatcher(
                newPathWatcher.trim(),
                newDestinationPathWatcher.trim()
            )
            setWatchers(prev => [...prev, watcher])
            setNewPathWatcher('')
            setNewDestinationPathWatcher('')
        } finally {
            setAddingWatcher(false)
        }
    }

    const handleAddScanner = async () => {
        if (!newPathScanner.trim()) return

        setAddingScanner(true)
        try {
            const scanner = await addFolderScanner(newPathScanner.trim())
            setScanners(prev => [...prev, scanner])
            setNewPathScanner('')
        } finally {
            setAddingScanner(false)
        }
    }

    const handleDelete = async (id: number) => {
        await deleteWatcher(id)
        setWatchers(prev => prev.filter(w => w.id !== id))
    }

    const handleDeleteScanner = async (id: number) => {
        await deleteFolderScanner(id)
        setScanners(prev => prev.filter(s => s.id !== id))
    }

    // 📁 folder picker
    // const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    //     const files = e.target.files
    //     if (!files || files.length === 0) return

    //     const firstFile = files[0] as any

    //     const relativePath = firstFile.webkitRelativePath || ''
    //     const rootFolder = relativePath.split('/')[0]

    //     setNewPath(rootFolder)
    //     setFolderPreview(relativePath)
    // }

    const getStatusClass = (status: string) => {
        switch (status.toLowerCase()) {
            case 'active':
                return 'status status--active'
            case 'error':
                return 'status status--error'
            case 'paused':
                return 'status status--paused'
            default:
                return 'status'
        }
    }

    return (
        <div className="watchers-page">

            {/* HEADER */}
            <div className="watchers-page__header">
                <h2>Watchers</h2>
                <span>{watchers.length} running</span>
            </div>

            {/* ADD SECTION */}
            <div className="watchers-page__add">

                {/* hidden file input */}
                <FolderSelector onSelect={setNewPathWatcher} />
                <FolderSelector onSelect={setNewDestinationPathWatcher} />

                <Button onClick={handleAddWatcher} disabled={addingWatcher || !newPathWatcher}>
                    {addingWatcher ? 'Adding...' : 'Add Watcher'}
                </Button>

            </div>

            {/* LOADING */}
            {loading && (
                <div className="watchers-page__center">
                    <Spinner size="lg" />
                </div>
            )}

            {/* LIST */}
            {!loading && (
                <div className="watchers-page__list">

                    {watchers.map(w => (
                        <div key={w.id} className="watcher-card">

                            <div className="watcher-card__main">

                                <div className="watcher-card__path">
                                    📁 Watched folder: {w.path}
                                </div>

                                <div className="watcher-card__meta">

                                    <span className={getStatusClass(w.status)}>
                                        {w.status}
                                    </span>

                                    <span className="watcher-card__time">
                                        {new Date(w.updated_at).toLocaleString()}
                                    </span>

                                </div>

                                <div className="watcher-card__path">
                                    📁 Destination: {w.destination_path}
                                </div>

                            </div>

                            <div className="watcher-card__actions">
                                <Button onClick={() => handleDelete(w.id)}>
                                    Delete
                                </Button>
                            </div>

                        </div>
                    ))}

                </div>
            )}

            {/* EMPTY */}
            {!loading && watchers.length === 0 && (
                <div className="watchers-page__center">
                    No watchers
                </div>
            )}

            {/* HEADER */}
            <div className="watchers-page__header">
                <h2>Scanners</h2>
                <span>{scanners.length} running</span>
            </div>

            {/* ADD SECTION */}
            <div className="watchers-page__add">

                {/* hidden file input */}
                <FolderSelector onSelect={setNewPathScanner} />

                <Button onClick={handleAddScanner} disabled={addingScanner || !newPathScanner}>
                    {addingScanner ? 'Adding...' : 'Add Scanner'}
                </Button>

            </div>

            {!loading && (
                <div className="watchers-page__list">

                    {scanners.map(s => (
                        <div key={s.id} className="watcher-card">

                            <div className="watcher-card__main">

                                <div className="watcher-card__path">
                                    📁 Scanned folder: {s.path}
                                </div>

                                <div className="watcher-card__meta">

                                    <span>
                                        Progress: {s.progress}
                                    </span>

                                </div>

                            </div>

                            <div className="watcher-card__actions">
                                <Button onClick={() => handleDelete(w.id)}>
                                    Delete
                                </Button>
                            </div>

                        </div>
                    ))}

                </div>
            )}

            {/* LOADING */}
            {loading && (
                <div className="watchers-page__center">
                    <Spinner size="lg" />
                </div>
            )}

        </div>
    )
}