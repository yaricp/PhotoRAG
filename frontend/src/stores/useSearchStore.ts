import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { SearchResult } from '@/types/api'

type SearchStore = {
    query: string
    results: SearchResult[]
    hasSearched: boolean

    setQuery: (q: string) => void
    setResults: (query: string, results: SearchResult[]) => void
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
