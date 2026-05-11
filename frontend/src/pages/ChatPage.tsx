import React, { useState, useRef, useEffect } from 'react'
import { sendChat, undoLastAction, archivePhoto, deletePhoto } from '@/api/client'
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

    const messagesEndRef = useRef<HTMLDivElement | null>(null)

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
            if (type === 'archive') await Promise.all(ids.map(id => archivePhoto(id)))
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
            const res = await sendChat({ message: finalMessage, thread_id: threadId ?? undefined })
            addMessage({ role: 'assistant', content: res.response })
            setThreadId(res.thread_id)
            if ((res as any).photos) setContextPhotos((res as any).photos)
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

    const isBusy = busyPhotoIds.size > 0
    const selCount = selectedPhotoIds.size

    const confirmTitle = pending?.type === 'delete'
        ? `Delete ${selCount} photo${selCount !== 1 ? 's' : ''}?`
        : `Archive ${selCount} photo${selCount !== 1 ? 's' : ''}?`
    const confirmMessage = pending?.type === 'delete'
        ? 'The files will be permanently removed from disk.'
        : 'The photos will be marked as archived.'

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
                                ? `${selCount} of ${contextPhotos.length} selected`
                                : 'Select all'}
                        </span>
                    </label>

                    {someSelected && (
                        <div className="chat-page__context-actions">
                            <button
                                className="chat-page__ctx-btn chat-page__ctx-btn--archive"
                                onClick={() => setPending({ type: 'archive', ids: [...selectedPhotoIds] })}
                                disabled={isBusy}
                            >
                                Archive
                            </button>
                            <button
                                className="chat-page__ctx-btn chat-page__ctx-btn--delete"
                                onClick={() => setPending({ type: 'delete', ids: [...selectedPhotoIds] })}
                                disabled={isBusy}
                            >
                                Delete
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
                        placeholder="Ask something about your photos..."
                    />
                    <button className="chat-page__undo-btn" onClick={onUndo} disabled={loading} title="Undo last action">
                        ↩ Undo
                    </button>
                    <button onClick={onSend} disabled={loading}>Send</button>
                    {messages.length > 0 && (
                        <button className="chat-page__clear-btn" onClick={clearConversation} disabled={loading} title="Start a new conversation">
                            New chat
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
