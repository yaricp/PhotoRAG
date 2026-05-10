import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { server } from '@/test/server'
import { http, HttpResponse } from 'msw'
import { useJobPolling } from '../useJobPolling'

vi.mock('@/api/base', () => ({ getBaseUrl: async () => 'http://localhost:8000' }))

describe('useJobPolling', () => {
    it('calls onComplete when job returns 404', async () => {
        server.use(
            http.get('http://localhost:8000/api/job/:photoId', () =>
                new HttpResponse(null, { status: 404 })
            )
        )
        const onComplete = vi.fn()
        vi.useFakeTimers()

        renderHook(() => useJobPolling(1, onComplete))
        await act(async () => { vi.advanceTimersByTime(3100) })
        expect(onComplete).toHaveBeenCalledTimes(1)

        vi.useRealTimers()
    })

    it('does not call onComplete when job still processing', async () => {
        const onComplete = vi.fn()
        vi.useFakeTimers()

        renderHook(() => useJobPolling(1, onComplete))
        await act(async () => { vi.advanceTimersByTime(3100) })
        expect(onComplete).not.toHaveBeenCalled()

        vi.useRealTimers()
    })

    it('cleans up interval on unmount', async () => {
        const onComplete = vi.fn()
        vi.useFakeTimers()

        const { unmount } = renderHook(() => useJobPolling(1, onComplete))
        unmount()
        await act(async () => { vi.advanceTimersByTime(6000) })
        expect(onComplete).not.toHaveBeenCalled()

        vi.useRealTimers()
    })
})