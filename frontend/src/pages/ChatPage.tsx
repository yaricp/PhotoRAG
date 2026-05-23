import React, { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { sendChat, undoLastAction, archivePhotos, deletePhoto, getSystemStatus } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { ConfirmModal } from '@/components/ui/ConfirmModal'
import { useChatStore } from '@/stores/useChatStore'
import './ChatPage.css'

type PendingAction = { type: 'archive' | 'delete'; ids: number[] } | null

export function ChatPage() {
    const { messages, threadId, contextPhotos, addMessage, setThreadId, setContextPhotos, clearConversation } =
        useChatStore()

    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [selectedPhotoIds, setSelectedPhotoIds] = useState<Set<number>>(new Set())
    const [busyPhotoIds, setBusyPhotoIds] = useState<Set<number>>(new Set())
    const [pending, setPending] = useState<PendingAction>(null)
    const [chatReady, setChatReady] = useState<boolean | null>(null)
    const [bannerDismissed, setBannerDismissed] = useState(false)

    const messagesEndRef = useRef<HTMLDivElement | null>(null)
    const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

    const stopPolling = useCallback(() => {
        if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current)
            pollTimerRef.current = null
        }
    }, [])

    useEffect(() => {
        let cancelled = false
        const check = async () => {
            try {
                const status = await getSystemStatus()
                if (cancelled) return
                setChatReady(status.chat_ready)
                if (status.chat_ready) stopPolling()
            } catch {
                // ignore network errors during polling
            }
        }
        check()
        pollTimerRef.current = setInterval(check, 5000)
        return () => {
            cancelled = true
            stopPolling()
        }
    }, [stopPolling])

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, loading])

    useEffect(() => {
        setSelectedPhotoIds(new Set())
    }, [contextPhotos])

    const allIds = contextPhotos.map(p => p.id)
    const allSelected = allIds.length > 0 && allIds.every(id => selectedPhotoIds.has(id))
    const someSelected = selectedPhotoIds.size > 0

    function toggleSelectAll() {
        setSelectedPhotoIds(allSelected ? new Set() : new Set(allIds))
    }

    function togglePhoto(id: number) {
        setSelectedPhotoIds(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
    }

    function removeFromContext(ids: number[]) {
        setContextPhotos(contextPhotos.filter(p => !ids.includes(p.id)))
        setSelectedPhotoIds(prev => {
            const next = new Set(prev)
            ids.forEach(id => next.delete(id))
            return next
        })
    }

    async function executeAction(action: PendingAction) {
        if (!action) return
        const { type, ids } = action
        setBusyPhotoIds(new Set(ids))
        try {
            if (type === 'archive') await archivePhotos(ids)
            else await Promise.all(ids.map(id => deletePhoto(id)))
            removeFromContext(ids)
        } finally {
            setBusyPhotoIds(new Set())
        }
    }

    const onSend = async () => {
        if (!input.trim() || loading) return

        const finalMessage = selectedPhotoIds.size > 0
            ? `${input.trim()}\n\n[Selected photo IDs: ${[...selectedPhotoIds].join(', ')}]`
            : input.trim()

        addMessage({ role: 'user', content: finalMessage })
        setInput('')
        setLoading(true)

        try {
            const res = await sendChat({ message: finalMessage, thread_id: threadId })
            addMessage({ role: 'assistant', content: res.response })
            setThreadId(res.thread_id)
            if (res.photos.length > 0) setContextPhotos(res.photos)
            // Model is clearly ready once a response arrives
            setChatReady(true)
            stopPolling()
        } catch (err) {
            const msg = err instanceof Error ? err.message : 'Unknown error'
            addMessage({ role: 'assistant', content: `⚠️ ${msg}` })
        } finally {
            setLoading(false)
        }
    }

    const onUndo = async () => {
        try {
            const result = await undoLastAction()
            addMessage({ role: 'assistant', content: `↩ ${result.detail}` })
        } catch {
            addMessage({ role: 'assistant', content: 'Undo failed.' })
        }
    }

    const { t } = useTranslation()

    const isBusy = busyPhotoIds.size > 0
    const selCount = selectedPhotoIds.size

    const plural = selCount !== 1 ? 's' : ''
    const confirmTitle = pending?.type === 'delete'
        ? t('chat.confirmDeleteTitle', { count: selCount, plural })
        : t('chat.confirmArchiveTitle', { count: selCount, plural })
    const confirmMessage = pending?.type === 'delete'
        ? t('chat.confirmDeleteMessage')
        : t('chat.confirmArchiveMessage')

    return (
        <div className="chat-page">

            {/* LEFT — context panel */}
            <div className="chat-page__context">

                {/* Sticky toolbar */}
                <div className="chat-page__context-toolbar">
                    <label className="chat-page__select-all">
                        <input
                            type="checkbox"
                            checked={allSelected}
                            ref={el => { if (el) el.indeterminate = someSelected && !allSelected }}
                            onChange={toggleSelectAll}
                            disabled={contextPhotos.length === 0}
                        />
                        <span>
                            {someSelected
                                ? t('chat.selected', { count: selCount, total: contextPhotos.length })
                                : t('chat.selectAll')}
                        </span>
                    </label>

                    {someSelected && (
                        <div className="chat-page__context-actions">
                            <button
                                className="chat-page__ctx-btn chat-page__ctx-btn--archive"
                                onClick={() => setPending({ type: 'archive', ids: [...selectedPhotoIds] })}
                                disabled={isBusy}
                            >
                                {t('chat.archive')}
                            </button>
                            <button
                                className="chat-page__ctx-btn chat-page__ctx-btn--delete"
                                onClick={() => setPending({ type: 'delete', ids: [...selectedPhotoIds] })}
                                disabled={isBusy}
                            >
                                {t('chat.delete')}
                            </button>
                        </div>
                    )}
                </div>

                {/* Scrollable photos */}
                <div className="chat-page__photos">
                    {contextPhotos.map(photo => (
                        <label
                            key={photo.id}
                            className={`chat-photo-item${busyPhotoIds.has(photo.id) ? ' chat-photo-item--busy' : ''}`}
                        >
                            <input
                                type="checkbox"
                                className="chat-photo-item__checkbox"
                                checked={selectedPhotoIds.has(photo.id)}
                                onChange={() => togglePhoto(photo.id)}
                            />
                            <PhotoCard photo={photo} />
                        </label>
                    ))}
                </div>
            </div>

            {/* RIGHT — chat */}
            <div className="chat-page__chat">
                {chatReady === false && !bannerDismissed && (
                    <div className="chat-page__warming-banner">
                        <Spinner size="sm" />
                        <span>{t('chat.warming')}</span>
                        <button className="chat-page__warming-dismiss" onClick={() => setBannerDismissed(true)}>✕</button>
                    </div>
                )}
                <div className="chat-page__messages">
                    {messages.map((m, i) => (
                        <div key={i} className={`chat-bubble chat-bubble--${m.role}`}>
                            {m.content}
                        </div>
                    ))}
                    {loading && <div className="chat-page__typing"><Spinner size="sm" /></div>}
                    <div ref={messagesEndRef} />
                </div>

                <div className="chat-page__input">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSend() }
                        }}
                        placeholder={t('chat.placeholder')}
                    />
                    <button className="chat-page__undo-btn" onClick={onUndo} disabled={loading} title={t('chat.undo')}>
                        {t('chat.undo')}
                    </button>
                    <button onClick={onSend} disabled={loading}>{t('chat.send')}</button>
                    {messages.length > 0 && (
                        <button className="chat-page__clear-btn" onClick={clearConversation} disabled={loading}>
                            {t('chat.newChat')}
                        </button>
                    )}
                </div>
            </div>

            <ConfirmModal
                open={pending !== null}
                title={confirmTitle}
                message={confirmMessage}
                confirmLabel={pending?.type === 'delete' ? 'Delete' : 'Archive'}
                variant={pending?.type === 'delete' ? 'danger' : 'warning'}
                onConfirm={() => executeAction(pending)}
                onClose={() => setPending(null)}
            />
        </div>
    )
}
