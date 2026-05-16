import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Photo } from '@/types/api'

export type ChatMessage = {
    role: 'user' | 'assistant'
    content: string
}

type ChatStore = {
    messages: ChatMessage[]
    threadId: string
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
            threadId: crypto.randomUUID(),
            contextPhotos: [],

            addMessage: (msg) =>
                set((s) => ({ messages: [...s.messages, msg] })),

            setThreadId: (id) => set({ threadId: id }),

            setContextPhotos: (photos) => set({ contextPhotos: photos }),

            clearConversation: () =>
                set({ messages: [], threadId: crypto.randomUUID(), contextPhotos: [] }),
        }),
        {
            name: 'chat-session',
            partialize: (s) => ({
                messages: s.messages,
                threadId: s.threadId,
                contextPhotos: s.contextPhotos,
            }),
            // Migrate stale persisted state that may have threadId: null
            onRehydrateStorage: () => (state) => {
                if (state && !state.threadId) {
                    state.threadId = crypto.randomUUID()
                }
            },
        }
    )
)
