import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Photo } from '@/types/api'

export type ChatMessage = {
    role: 'user' | 'assistant'
    content: string
}

type ChatStore = {
    messages: ChatMessage[]
    threadId: string | null
    contextPhotos: Photo[]

    addMessage: (msg: ChatMessage) => void
    setThreadId: (id: string) => void
    setContextPhotos: (photos: Photo[]) => void
    clearConversation: () => void
}

export const useChatStore = create<ChatStore>()(
    persist(
        (set) => ({
            messages: [],
            threadId: null,
            contextPhotos: [],

            addMessage: (msg) =>
                set((s) => ({ messages: [...s.messages, msg] })),

            setThreadId: (id) => set({ threadId: id }),

            setContextPhotos: (photos) => set({ contextPhotos: photos }),

            clearConversation: () =>
                set({ messages: [], threadId: null, contextPhotos: [] }),
        }),
        {
            name: 'chat-session',
            // Only persist these fields — selectedPhotoIds is UI-transient
            partialize: (s) => ({
                messages: s.messages,
                threadId: s.threadId,
                contextPhotos: s.contextPhotos,
            }),
        }
    )
)
