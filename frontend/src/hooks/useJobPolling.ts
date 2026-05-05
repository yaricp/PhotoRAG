import { useEffect } from 'react'
import { getBaseUrl } from '@/api/base'

export function useJobPolling(photoId: number, onComplete: () => void) {
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const base = await getBaseUrl()
                const res = await fetch(`${base}/api/job/${photoId}`)
                if (res.status === 404) {
                    clearInterval(interval)
                    onComplete()
                }
            } catch {
                // network error — keep polling
            }
        }, 3000)
        return () => clearInterval(interval)
    }, [photoId, onComplete])
}