import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
    getWatchers, addWatcher, deleteWatcher,
    getFolderScanners, addFolderScanner, deleteFolderScanner,
} from '@/api/client'
import { Spinner } from '@/components/ui/Spinner'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { FolderSelector } from '@/components/ui/FolderSelector'
import type { FolderScanner, Watcher } from '@/types/api'
import './FoldersPage.css'

export function FoldersPage() {
    const { t } = useTranslation()
    const [watchers, setWatchers] = useState<Watcher[]>([])
    const [scanners, setScanners] = useState<FolderScanner[]>([])
    const [loading, setLoading] = useState(true)

    const [newWatchSrc, setNewWatchSrc] = useState('')
    const [newWatchDst, setNewWatchDst] = useState('')
    const [addingWatcher, setAddingWatcher] = useState(false)

    const [newScanPath, setNewScanPath] = useState('')
    const [addingScanner, setAddingScanner] = useState(false)

    const load = async () => {
        try {
            const [w, s] = await Promise.all([getWatchers(), getFolderScanners()])
            setWatchers(w)
            setScanners(s)
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
        if (!newWatchSrc.trim()) return
        setAddingWatcher(true)
        try {
            const w = await addWatcher(newWatchSrc.trim(), newWatchDst.trim())
            setWatchers(prev => [...prev, w])
            setNewWatchSrc('')
            setNewWatchDst('')
        } finally {
            setAddingWatcher(false)
        }
    }

    const handleAddScanner = async () => {
        if (!newScanPath.trim()) return
        setAddingScanner(true)
        try {
            const s = await addFolderScanner(newScanPath.trim())
            setScanners(prev => [...prev, s])
            setNewScanPath('')
        } finally {
            setAddingScanner(false)
        }
    }

    return (
        <div className="folders-page">
            <h1 className="page-title">{t('folders.title')}</h1>

            {/* ── WATCHERS ─────────────────────────────── */}
            <hr className="border border-gray-700" />
            <section className="folders-section">
                <div className="folders-section__header">
                    <div>
                        <h2 className="folders-section__title">{t('folders.watchers')}</h2>
                        <p className="folders-section__desc">{t('folders.watchersDesc')}</p>
                    </div>
                    <span className="folders-section__count">{t('folders.activeCount', { count: watchers.length })}</span>
                </div>

                <div className="folders-add-form">
                    <div className="folders-add-form__row">
                        <div className="folders-add-form__field">
                            <label className="folders-add-form__label">{t('folders.sourceFolder')}</label>
                            <FolderSelector onSelect={setNewWatchSrc} />
                            {newWatchSrc && <p className="folders-add-form__path">{newWatchSrc}</p>}
                        </div>
                        <div className="folders-add-form__arrow">→</div>
                        <div className="folders-add-form__field">
                            <label className="folders-add-form__label">{t('folders.destinationFolder')}</label>
                            <FolderSelector onSelect={setNewWatchDst} />
                            {newWatchDst && <p className="folders-add-form__path">{newWatchDst}</p>}
                        </div>
                        <Button
                            onClick={handleAddWatcher}
                            disabled={addingWatcher || !newWatchSrc || !newWatchDst}
                            loading={addingWatcher}
                        >
                            {t('folders.addButton')}
                        </Button>
                    </div>
                </div>

                {loading && <div className="folders-center"><Spinner size="lg" /></div>}

                {!loading && watchers.length === 0 && (
                    <div className="folders-empty">{t('folders.noWatchers')}</div>
                )}

                {!loading && watchers.length > 0 && (
                    <div className="folders-list">
                        {watchers.map(w => (
                            <WatcherCard
                                key={w.id}
                                watcher={w}
                                onDelete={() => {
                                    deleteWatcher(w.id)
                                    setWatchers(prev => prev.filter(x => x.id !== w.id))
                                }}
                            />
                        ))}
                    </div>
                )}
            </section>

            <div className="folders-divider" />

            {/* ── SCANNERS ─────────────────────────────── */}

            <hr className="border border-gray-700" />
            <section className="folders-section">
                <div className="folders-section__header">
                    <div>
                        <h2 className="folders-section__title">{t('folders.scanners')}</h2>
                        <p className="folders-section__desc">{t('folders.scannersDesc')}</p>
                    </div>
                    <span className="folders-section__count">{t('folders.activeCount', { count: scanners.length })}</span>
                </div>

                <div className="folders-add-form">
                    <div className="folders-add-form__row">
                        <div className="folders-add-form__field">
                            <label className="folders-add-form__label">{t('folders.scanFolder')}</label>
                            <FolderSelector onSelect={setNewScanPath} />
                            {newScanPath && <p className="folders-add-form__path">{newScanPath}</p>}
                        </div>
                        <Button
                            onClick={handleAddScanner}
                            disabled={addingScanner || !newScanPath}
                            loading={addingScanner}
                        >
                            {t('folders.startScan')}
                        </Button>
                    </div>
                </div>

                {loading && <div className="folders-center"><Spinner size="lg" /></div>}

                {!loading && scanners.length === 0 && (
                    <div className="folders-empty">{t('folders.noScanners')}</div>
                )}

                {!loading && scanners.length > 0 && (
                    <div className="folders-list">
                        {scanners.map(s => (
                            <ScannerCard
                                key={s.id}
                                scanner={s}
                                onDelete={() => {
                                    deleteFolderScanner(s.id)
                                    setScanners(prev => prev.filter(x => x.id !== s.id))
                                }}
                            />
                        ))}
                    </div>
                )}
            </section>

        </div>
    )
}

function WatcherCard({ watcher: w, onDelete }: { watcher: Watcher; onDelete: () => void }) {
    const { t } = useTranslation()
    const statusVariant = w.status === 'active' ? 'success'
        : w.status === 'error' ? 'error'
            : 'processing'

    return (
        <div className="folder-card">
            <div className="folder-card__body">
                <div className="folder-card__paths">
                    <div className="folder-card__path-item">
                        <span className="folder-card__path-label">{t('folders.source')}</span>
                        <span className="folder-card__path-value">📁 {w.path}</span>
                    </div>
                    <div className="folder-card__path-arrow">→</div>
                    <div className="folder-card__path-item">
                        <span className="folder-card__path-label">{t('folders.target')}</span>
                        <span className="folder-card__path-value">📁 {w.destination_path}</span>
                    </div>
                </div>
                <div className="folder-card__meta">
                    <Badge variant={statusVariant}>{w.status}</Badge>
                    <span className="folder-card__time">
                        {t('folders.updatedAt')} {new Date(w.updated_at).toLocaleString()}
                    </span>
                </div>
            </div>
            <Button variant="danger" onClick={onDelete}>{t('folders.delete')}</Button>
        </div>
    )
}

function ScannerCard({ scanner: s, onDelete }: { scanner: FolderScanner; onDelete: () => void }) {
    const { t } = useTranslation()
    const progress = typeof s.progress === 'number' ? s.progress : 0
    const isDone = progress >= 100

    return (
        <div className="folder-card">
            <div className="folder-card__body">

                <div className="folder-card__path-item">
                    <span className="folder-card__path-label">{t('folders.scanningFolder')}</span>
                    <span className="folder-card__path-value">📁 {s.path}</span>
                </div>

                <div className="scanner-progress">
                    <div className="scanner-progress__header">
                        <span className="scanner-progress__label">
                            {isDone ? t('folders.done') : t('folders.scanning')}
                        </span>
                        <span className="scanner-progress__pct">{Math.round(progress)}%</span>
                    </div>
                    <div className="scanner-progress__track">
                        <div
                            className={`scanner-progress__bar${isDone ? ' scanner-progress__bar--done' : ''}`}
                            style={{ width: `${Math.min(progress, 100)}%` }}
                        />
                    </div>
                </div>

            </div>
            <Button variant="danger" onClick={onDelete}>{t('folders.delete')}</Button>
        </div>
    )
}
