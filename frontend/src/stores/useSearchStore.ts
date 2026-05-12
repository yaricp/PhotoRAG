import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { Photo } from '@/types/api'

type SearchStore = {
    query: string
    results: Photo[]
    hasSearched: boolean

    setQuery: (q: string) => void
    setResults: (query: string, results: Photo[]) => void
    clear: () => void
}

export const useSearchStore = create<SearchStore>()(
    persist(
        (set) => ({
            query: '',
            results: [],
            hasSearched: false,

            setQuery: (q) => set({ query: q }),
            setResults: (query, results) => set({ query, results, hasSearched: true }),
            clear: () => set({ query: '', results: [], hasSearched: false }),
        }),
        {
            name: 'search-session',
            storage: createJSONStorage(() => sessionStorage),
        }
    )
)
