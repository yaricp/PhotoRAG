import React, { useState, useRef, useEffect } from 'react'
import { sendChat, undoLastAction } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import { useChatStore } from '@/stores/useChatStore'
import './ChatPage.css'

export function ChatPage() {
    const { messages, threadId, contextPhotos, addMessage, setThreadId, setContextPhotos, clearConversation } =
        useChatStore()

    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const [selectedPhotoIds, setSelectedPhotoIds] = useState<Set<number>>(new Set())

    const messagesEndRef = useRef<HTMLDivElement | null>(null)

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, loading])

    // Reset selections when agent returns new context photos
    useEffect(() => {
        setSelectedPhotoIds(new Set())
    }, [contextPhotos])

    function togglePhoto(id: number) {
        setSelectedPhotoIds(prev => {
            const next = new Set(prev)
            next.has(id) ? next.delete(id) : next.add(id)
            return next
        })
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
            const res = await sendChat({
                message: finalMessage,
                thread_id: threadId ?? undefined,
            })

            addMessage({ role: 'assistant', content: res.response })
            setThreadId(res.thread_id)

            if ((res as any).photos) {
                setContextPhotos((res as any).photos)
            }

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

    return (
        <div className="chat-page">

            {/* LEFT */}
            <div className="chat-page__context">
                <div className="chat-page__context-title">
                    Related photos
                </div>

                <div className="chat-page__photos">
                    {contextPhotos.map(photo => (
                        <label key={photo.id} className="chat-photo-item">
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

            {/* RIGHT */}
            <div className="chat-page__chat">

                {/* MESSAGES */}
                <div className="chat-page__messages">
                    {messages.map((m, i) => (
                        <div
                            key={i}
                            className={`chat-bubble chat-bubble--${m.role}`}
                        >
                            {m.content}
                        </div>
                    ))}

                    {loading && (
                        <div className="chat-page__typing">
                            <Spinner size="sm" />
                        </div>
                    )}

                    <div ref={messagesEndRef} />
                </div>

                {/* INPUT */}
                <div className="chat-page__input">
                    <textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault()
                                onSend()
                            }
                        }}
                        placeholder="Ask something about your photos..."
                    />

                    <button
                        className="chat-page__undo-btn"
                        onClick={onUndo}
                        disabled={loading}
                        title="Undo last action"
                    >
                        ↩ Undo
                    </button>

                    <button onClick={onSend} disabled={loading}>
                        Send
                    </button>

                    {messages.length > 0 && (
                        <button
                            className="chat-page__clear-btn"
                            onClick={clearConversation}
                            disabled={loading}
                            title="Start a new conversation"
                        >
                            New chat
                        </button>
                    )}
                </div>
            </div>
        </div>
    )
}
