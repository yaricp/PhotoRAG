import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getModelConfigs } from '@/api/client'
import type { AIModelConfig } from '@/types/api'
import { StepDownloading } from './SetupWizard/StepDownloading'
import './SetupWizard/SetupWizard.css'
import './OllamaModelsPage.css'

type Inventory = Awaited<ReturnType<Window['electronAPI']['getOllamaInventory']>>

function formatBytes(value: number): string {
    if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`
    return `${(value / 1024 ** 2).toFixed(0)} MB`
}

export function OllamaModelsPage() {
    const { t } = useTranslation()
    const [inventory, setInventory] = useState<Inventory | null>(null)
    const [configs, setConfigs] = useState<AIModelConfig[]>([])
    const [loading, setLoading] = useState(true)
    const [deleting, setDeleting] = useState(false)
    const [newModel, setNewModel] = useState('')
    const [pullName, setPullName] = useState<string | null>(null)
    const [error, setError] = useState<string | null>(null)

    const refresh = useCallback(async () => {
        setLoading(true)
        try {
            const [nextInventory, nextConfigs] = await Promise.all([
                window.electronAPI.getOllamaInventory(), getModelConfigs(),
            ])
            setInventory(nextInventory)
            setConfigs(nextConfigs)
            setError(null)
        } catch (cause) {
            setError(t('ollamaManager.error', { error: String(cause) }))
        } finally {
            setLoading(false)
        }
    }, [t])

    useEffect(() => { void refresh() }, [refresh])

    const usedBy = (name: string) => configs
        .filter(config => config.mode === 'remote' && config.model_provider === 'ollama' &&
            (config.model_name === name || `${config.model_name}:latest` === name))
        .map(config => t(`wizard.stepModelConfig.label${config.type.charAt(0).toUpperCase()}${config.type.slice(1)}`, { defaultValue: config.type }))

    const remove = async (names: string[]) => {
        if (!inventory || names.length === 0) return
        const prompt = names.length === 1
            ? t('ollamaManager.confirmOne', { model: names[0] })
            : t('ollamaManager.confirmAll', { count: names.length })
        const assignments = names.flatMap(usedBy)
        if (!window.confirm(assignments.length ? `${prompt}\n${t('ollamaManager.used', { tasks: [...new Set(assignments)].join(', ') })}` : prompt)) return
        setDeleting(true)
        try {
            for (const model of names) await window.electronAPI.deleteOllamaModel({ model })
            await refresh()
        } catch (cause) {
            await refresh()
            setError(t('ollamaManager.deleteError', { error: String(cause) }))
        } finally {
            setDeleting(false)
        }
    }

    const free = inventory?.freeBytes
    const total = inventory?.totalBytes
    const lowDisk = free != null && total != null && (free < 5 * 1024 ** 3 || free / total < 0.1)

    return <main className="ollama-manager">
        <header className="ollama-manager__header">
            <div><h1>{t('ollamaManager.title')}</h1><p>{t('ollamaManager.subtitle')}</p></div>
            <button type="button" onClick={() => void refresh()} disabled={loading || deleting}>{t('ollamaManager.refresh')}</button>
        </header>
        {loading && <p>{t('ollamaManager.loading')}</p>}
        {error && <p role="alert" className="ollama-manager__warning">{error}</p>}
        <form className="ollama-manager__install" onSubmit={event => {
            event.preventDefault()
            if (newModel.trim()) setPullName(newModel.trim())
        }}>
            <label htmlFor="ollama-model-name">{t('ollamaManager.downloadLabel')}</label>
            <input id="ollama-model-name" value={newModel} onChange={event => setNewModel(event.target.value)}
                placeholder="qwen3-vl:4b-instruct" />
            <button type="submit" disabled={!newModel.trim() || !!pullName}>{t('ollamaManager.download')}</button>
        </form>
        {pullName && <div className="ollama-manager__overlay">
            <div className="ollama-manager__download" role="dialog" aria-modal="true">
                <StepDownloading selectedModels={new Set()} ollamaModels={[{ name: pullName }]}
                    onDone={() => { setPullName(null); setNewModel(''); void refresh() }}
                    onBack={() => setPullName(null)} />
            </div>
        </div>}
        {inventory && <>
            <div className="ollama-manager__summary">
                <p>{t('ollamaManager.free')}: <strong>{free == null ? '—' : formatBytes(free)}</strong></p>
                <p>{t('ollamaManager.total', { size: formatBytes(inventory.models.reduce((sum, model) => sum + model.size, 0)) })}</p>
                {inventory.storagePath
                    ? <p>{t('ollamaManager.disk', { path: inventory.storagePath })}</p>
                    : <p>{t('ollamaManager.unknown')}</p>}
                {!inventory.storageVerified && inventory.storagePath && <p>{t('ollamaManager.estimate')}</p>}
                <p>{t('ollamaManager.shared')}</p>
            </div>
            {lowDisk && <p role="status" className="ollama-manager__warning">{t('ollamaManager.low')}</p>}
            {inventory.models.length === 0 ? <p>{t('ollamaManager.empty')}</p> : <>
                <div className="ollama-manager__actions">
                    <button type="button" onClick={() => void remove(inventory.models.map(model => model.name))} disabled={deleting}>
                        {deleting ? t('ollamaManager.deleting') : t('ollamaManager.deleteAll')}
                    </button>
                </div>
                <ul className="ollama-manager__list">{inventory.models.map(model => {
                    const tasks = usedBy(model.name)
                    return <li key={model.name}>
                        <div><strong>{model.name}</strong><p>{t('ollamaManager.size')}: {formatBytes(model.size)}</p>
                            <p>{tasks.length ? t('ollamaManager.used', { tasks: tasks.join(', ') }) : t('ollamaManager.unused')}</p></div>
                        <button type="button" onClick={() => void remove([model.name])} disabled={deleting}>{t('ollamaManager.delete')}</button>
                    </li>
                })}</ul>
            </>}
        </>}
    </main>
}
