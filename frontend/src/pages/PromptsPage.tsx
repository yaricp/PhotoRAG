import React, { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { getPrompts, updatePrompt } from '@/api/client'
import type { Prompt } from '@/types/api'
import './PromptsPage.css'

interface PromptState {
    text: string
    saving: boolean
    saved: boolean
    error: string | null
}

export function PromptsPage() {
    const { t } = useTranslation()
    const [prompts, setPrompts] = useState<Prompt[]>([])
    const [loading, setLoading] = useState(true)
    const [states, setStates] = useState<Record<string, PromptState>>({})

    useEffect(() => {
        getPrompts()
            .then(data => {
                setPrompts(data)
                const initial: Record<string, PromptState> = {}
                data.forEach(p => {
                    initial[p.key] = { text: p.text, saving: false, saved: false, error: null }
                })
                setStates(initial)
            })
            .finally(() => setLoading(false))
    }, [])

    function setText(key: string, text: string) {
        setStates(prev => ({ ...prev, [key]: { ...prev[key], text, saved: false, error: null } }))
    }

    async function handleSave(key: string) {
        const text = states[key]?.text ?? ''
        setStates(prev => ({ ...prev, [key]: { ...prev[key], saving: true, error: null } }))
        try {
            const updated = await updatePrompt(key, text)
            setPrompts(prev => prev.map(p => p.key === key ? updated : p))
            setStates(prev => ({ ...prev, [key]: { text: updated.text, saving: false, saved: true, error: null } }))
            setTimeout(() => {
                setStates(prev => ({ ...prev, [key]: { ...prev[key], saved: false } }))
            }, 2500)
        } catch (e: any) {
            setStates(prev => ({ ...prev, [key]: { ...prev[key], saving: false, error: e.message ?? 'Save failed' } }))
        }
    }

    if (loading) {
        return <div className="prompts-page"><p className="prompts-loading">{t('prompts.loading')}</p></div>
    }

    const groups = Array.from(new Set(prompts.map(p => p.group))).sort()

    return (
        <div className="prompts-page">
            <h1 className="prompts-page__title">{t('prompts.title')}</h1>
            <p className="prompts-page__subtitle">{t('prompts.subtitle')}</p>

            {groups.map(group => (
                <section key={group} className="prompts-group">
                    <h2 className="prompts-group__name">{group.replace('_', ' ')}</h2>
                    {prompts
                        .filter(p => p.group === group)
                        .map(p => {
                            const s = states[p.key]
                            const dirty = s?.text !== p.text
                            return (
                                <div key={p.key} className="prompt-card">
                                    <div className="prompt-card__header">
                                        <span className="prompt-card__title">{p.title}</span>
                                        <code className="prompt-card__key">{p.key}</code>
                                    </div>
                                    {p.description && (
                                        <p className="prompt-card__desc">{p.description}</p>
                                    )}
                                    <textarea
                                        className="prompt-card__textarea"
                                        value={s?.text ?? ''}
                                        onChange={e => setText(p.key, e.target.value)}
                                        rows={6}
                                        spellCheck={false}
                                    />
                                    <div className="prompt-card__footer">
                                        <button
                                            className="prompt-card__save-btn"
                                            onClick={() => handleSave(p.key)}
                                            disabled={s?.saving || !dirty}
                                        >
                                            {s?.saving ? t('prompts.saving') : t('prompts.save')}
                                        </button>
                                        {s?.saved && <span className="prompt-card__saved">{t('prompts.saved')}</span>}
                                        {s?.error && <span className="prompt-card__error">{s.error}</span>}
                                    </div>
                                </div>
                            )
                        })
                    }
                </section>
            ))}
        </div>
    )
}
