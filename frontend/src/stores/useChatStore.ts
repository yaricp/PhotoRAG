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
    draftInput: string
    selectedPhotoIds: number[]

    addMessage: (msg: ChatMessage) => void
    setThreadId: (id: string) => void
    setContextPhotos: (photos: Photo[]) => void
    setDraftInput: (input: string) => void
    setSelectedPhotoIds: (ids: number[]) => void
    clearConversation: () => void
}

export const useChatStore = create<ChatStore>()(
    persist(
        (set) => ({
            messages: [],
            threadId: crypto.randomUUID(),
            contextPhotos: [],
            draftInput: '',
            selectedPhotoIds: [],

            addMessage: (msg) =>
                set((s) => ({ messages: [...s.messages, msg] })),

            setThreadId: (id) => set({ threadId: id }),

            setContextPhotos: (photos) => set({ contextPhotos: photos }),

            setDraftInput: (input) => set({ draftInput: input }),

            setSelectedPhotoIds: (ids) => set({ selectedPhotoIds: ids }),

            clearConversation: () =>
                set({
                    messages: [],
                    threadId: crypto.randomUUID(),
                    contextPhotos: [],
                    draftInput: '',
                    selectedPhotoIds: [],
                }),
        }),
        {
            name: 'chat-session',
            partialize: (s) => ({
                messages: s.messages,
                threadId: s.threadId,
                contextPhotos: s.contextPhotos,
                draftInput: s.draftInput,
                selectedPhotoIds: s.selectedPhotoIds,
            }),
            // Migrate stale persisted state that may have threadId: null
            onRehydrateStorage: () => (state) => {
                if (state && !state.threadId) {
                    state.threadId = crypto.randomUUID()
                }
                if (state && !Array.isArray(state.selectedPhotoIds)) {
                    state.selectedPhotoIds = []
                }
                if (state && typeof state.draftInput !== 'string') {
                    state.draftInput = ''
                }
            },
        }
    )
)
