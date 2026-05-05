import React, { useState, useRef, useEffect } from 'react'
import { sendChat } from '@/api/client'
import { PhotoCard } from '@/components/photos/PhotoCard'
import { Spinner } from '@/components/ui/Spinner'
import type { Photo } from '@/types/api'
import './ChatPage.css'

type Message = {
    role: 'user' | 'assistant'
    content: string
}

export function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)

    const [contextPhotos, setContextPhotos] = useState<Photo[]>([])
    const [threadId, setThreadId] = useState<string | null>(null)

    const messagesEndRef = useRef<HTMLDivElement | null>(null)

    // ✅ AUTO SCROLL
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({
            behavior: 'smooth'
        })
    }, [messages, loading])

    const onSend = async () => {
        if (!input.trim() || loading) return

        const userMsg = { role: 'user', content: input }

        setMessages(prev => [...prev, userMsg])
        setInput('')
        setLoading(true)

        try {
            const res = await sendChat({
                message: input,
                thread_id: threadId ?? undefined,
            })

            setMessages(prev => [
                ...prev,
                { role: 'assistant', content: res.response }
            ])

            setThreadId(res.thread_id)

            // если позже добавишь фото
            if ((res as any).photos) {
                setContextPhotos((res as any).photos)
            }

        } finally {
            setLoading(false)
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
                        <PhotoCard key={photo.id} photo={photo} />
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

                    {/* anchor */}
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

                    <button onClick={onSend} disabled={loading}>
                        Send
                    </button>
                </div>
            </div>
        </div>
    )
}