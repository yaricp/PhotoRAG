import React, { useEffect, useState } from 'react'
import { getWatchers, addWatcher, deleteWatcher } from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { FolderSelector } from '@/components/ui/FolderSelector'
import './WatchersPage.css'

export interface Watcher {
    id: number
    path: string
    status: string
    updated_at: string
}

export function WatchersPage() {
    const [watchers, setWatchers] = useState<Watcher[]>([])
    const [loading, setLoading] = useState(true)

    const [newPath, setNewPath] = useState('')
    const [folderPreview, setFolderPreview] = useState('')
    const [adding, setAdding] = useState(false)

    const load = async () => {
        try {
            const data = await getWatchers()
            setWatchers(data)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        load()
        const interval = setInterval(load, 5000)
        return () => clearInterval(interval)
    }, [])

    const handleAdd = async () => {
        if (!newPath.trim()) return

        setAdding(true)
        try {
            const watcher = await addWatcher(newPath.trim())
            setWatchers(prev => [...prev, watcher])
            setNewPath('')
            setFolderPreview('')
        } finally {
            setAdding(false)
        }
    }

    const handleDelete = async (id: number) => {
        await deleteWatcher(id)
        setWatchers(prev => prev.filter(w => w.id !== id))
    }

    // 📁 folder picker
    const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files
        if (!files || files.length === 0) return

        const firstFile = files[0] as any

        const relativePath = firstFile.webkitRelativePath || ''
        const rootFolder = relativePath.split('/')[0]

        setNewPath(rootFolder)
        setFolderPreview(relativePath)
    }

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
                <FolderSelector onSelect={setNewPath} />

                <Button onClick={handleAdd} disabled={adding || !newPath}>
                    {adding ? 'Adding...' : 'Add'}
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
                                    📁 {w.path}
                                </div>

                                <div className="watcher-card__meta">

                                    <span className={getStatusClass(w.status)}>
                                        {w.status}
                                    </span>

                                    <span className="watcher-card__time">
                                        {new Date(w.updated_at).toLocaleString()}
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

            {/* EMPTY */}
            {!loading && watchers.length === 0 && (
                <div className="watchers-page__center">
                    No watchers
                </div>
            )}

        </div>
    )
}